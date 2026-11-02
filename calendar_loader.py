import re
import urllib.request
import urllib.error
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from holidays_manager import now_madrid


logger = logging.getLogger(__name__)

DAYS_SPANISH = [
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
]

def parse_ics_datetime(val_str: str) -> datetime:
    """Parsea una cadena de fecha/hora de iCal (ej: 20261018T100000Z o 20261018)."""
    val_str = val_str.strip()
    # Si viene con parámetros tipo DTSTART;VALUE=DATE:20261007
    if ":" in val_str:
        val_str = val_str.split(":")[-1].strip()

    try:
        if "T" in val_str:
            # Formato UTC (ej: 20261018T100000Z)
            if val_str.endswith("Z"):
                dt = datetime.strptime(val_str, "%Y%m%dT%H%M%SZ")
                # Convertir a hora peninsular de España y quitar tzinfo para comparaciones homogéneas
                try:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
                except Exception:
                    dt = dt + timedelta(hours=2)
                return dt
            else:
                return datetime.strptime(val_str[:15], "%Y%m%dT%H%M%S")
        else:
            # Solo fecha (ej: 20261018)
            d = datetime.strptime(val_str[:8], "%Y%m%d")
            return d
    except Exception as e:
        logger.debug(f"Error parseando fecha ical '{val_str}': {e}")
        return None

def fetch_calendar_events(ics_url: str, timeout: int = 10) -> list[dict]:
    """
    Descarga y parsea los eventos de un calendario en formato iCal (.ics).
    Retorna una lista de diccionarios con {summary, start, end, is_all_day, location, description}.
    """
    if not ics_url or not ics_url.strip():
        return []

    url = ics_url.strip()
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AlvaroMenuApp/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_data = response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"Error descargando calendario iCal desde '{url[:40]}...': {e}")
        return []

    events = []
    # Separar bloques VEVENT
    raw_events = raw_data.split("BEGIN:VEVENT")

    for block in raw_events[1:]:
        end_idx = block.find("END:VEVENT")
        if end_idx != -1:
            block = block[:end_idx]

        summary = ""
        start_dt = None
        end_dt = None
        is_all_day = False
        location = ""
        description = ""

        # Unir líneas continuas (RFC 5545 especifica que líneas que empiezan por espacio o tab son continuación)
        unfolded_lines = []
        for line in block.splitlines():
            if line.startswith(" ") or line.startswith("\t"):
                if unfolded_lines:
                    unfolded_lines[-1] += line[1:]
            else:
                unfolded_lines.append(line)

        for line in unfolded_lines:
            line_clean = line.strip()
            if line_clean.startswith("SUMMARY:"):
                summary = line_clean[8:].strip()
            elif line_clean.startswith("SUMMARY;"):
                summary = line_clean.split(":", 1)[-1].strip()
            elif line_clean.startswith("DTSTART"):
                is_all_day = ("VALUE=DATE" in line_clean and "T" not in line_clean)
                start_dt = parse_ics_datetime(line_clean)
            elif line_clean.startswith("DTEND"):
                end_dt = parse_ics_datetime(line_clean)
            elif line_clean.startswith("LOCATION:"):
                location = line_clean[9:].strip()
            elif line_clean.startswith("DESCRIPTION:"):
                description = line_clean[12:].strip()

        # Decodificar secuencias de escape típicas de iCal
        summary = summary.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").strip()
        location = location.replace("\\,", ",").replace("\\;", ";").strip()

        if summary and start_dt:
            events.append({
                "summary": summary,
                "start": start_dt,
                "end": end_dt or start_dt,
                "is_all_day": is_all_day,
                "location": location,
                "description": description
            })

    # Ordenar cronológicamente
    events.sort(key=lambda x: x["start"] if x["start"] else datetime.min)
    return events

def _event_occurs_on_date(ev: dict, target_date: date) -> bool:
    """Comprueba si un evento (de un día o de varios días) tiene lugar en target_date."""
    ev_start = ev.get("start")
    if not ev_start:
        return False
    start_date = ev_start.date() if isinstance(ev_start, datetime) else ev_start

    ev_end = ev.get("end")
    if not ev_end:
        return start_date == target_date
    end_date = ev_end.date() if isinstance(ev_end, datetime) else ev_end

    if ev.get("is_all_day") and end_date > start_date:
        # En RFC 5545, DTEND para eventos VALUE=DATE es exclusivo
        last_inclusive_date = end_date - timedelta(days=1)
    else:
        last_inclusive_date = max(start_date, end_date)

    return start_date <= target_date <= last_inclusive_date

def get_events_for_current_week(events: list[dict], now: datetime = None) -> dict[str, list[dict]]:
    """
    Agrupa los eventos correspondientes a cada día de la semana actual (Lunes a Domingo).
    Retorna un diccionario: {'Lunes': [evento1, ...], 'Martes': [...], ...}
    """
    if now is None:
        now = now_madrid()

    # Calcular el Lunes de la semana actual (Lunes=0, ..., Domingo=6)
    monday = (now - timedelta(days=now.weekday())).date()
    
    week_map = {}
    for i, day_name in enumerate(DAYS_SPANISH):
        day_date = monday + timedelta(days=i)
        day_events = [ev for ev in events if _event_occurs_on_date(ev, day_date)]
        week_map[day_name] = {
            "date": day_date,
            "date_str": day_date.strftime("%d/%m"),
            "events": day_events
        }

    return week_map

def get_events_for_menu_week(events: list[dict], now: datetime = None) -> dict[str, dict]:
    """
    Agrupa los eventos correspondientes a la semana del menú planificado (Lunes a Domingo).
    Si hoy es Sábado o Domingo (fin de semana de planificación), la semana del menú
    es el Lunes entrante al Domingo siguiente.
    Si hoy es Lunes a Viernes (semana en curso), es el Lunes de esta semana al Domingo.
    """
    if now is None:
        now = now_madrid()

    # Si es fin de semana (Sábado=5, Domingo=6), el menú aplica al Lunes siguiente
    if now.weekday() == 5:
        monday = (now + timedelta(days=2)).date()
    elif now.weekday() == 6:
        monday = (now + timedelta(days=1)).date()
    else:
        monday = (now - timedelta(days=now.weekday())).date()
    
    week_map = {}
    for i, day_name in enumerate(DAYS_SPANISH):
        day_date = monday + timedelta(days=i)
        day_events = [ev for ev in events if _event_occurs_on_date(ev, day_date)]
        week_map[day_name] = {
            "date": day_date,
            "date_str": day_date.strftime("%d/%m"),
            "events": day_events
        }

    return week_map

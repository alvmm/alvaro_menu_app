import urllib.parse
from datetime import datetime, date, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

def generate_menu_ics(menu_data: list, calendar_name: str = "Menú Semanal AyA") -> str:
    """
    Genera un archivo de calendario iCal (.ics) conforme a RFC 5545 con todos los
    almuerzos y cenas de la semana para importar en Google Calendar / Apple Calendar.
    """
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Alvaro y Ana//Menu Semanal AyA//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{calendar_name}",
        "X-WR-TIMEZONE:Europe/Madrid",
        "BEGIN:VTIMEZONE",
        "TZID:Europe/Madrid",
        "X-LIC-LOCATION:Europe/Madrid",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0200",
        "TZOFFSETTO:+0100",
        "TZNAME:CET",
        "DTSTART:19701025T030000",
        "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
        "END:STANDARD",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:+0100",
        "TZOFFSETTO:+0200",
        "TZNAME:CEST",
        "DTSTART:19700329T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        "END:DAYLIGHT",
        "END:VTIMEZONE"
    ]

    for entry in menu_data:
        day_name = entry.get("day", "")
        day_date_str = entry.get("date", "")
        if not day_date_str:
            continue

        clean_date = day_date_str.replace("-", "")

        # 1. Evento Almuerzo (14:00 a 15:00)
        comida = entry.get("comida", {})
        c_name = comida.get("name", "Comida")
        c_ing = comida.get("ingredients", "")
        c_desc = f"Ingredientes: {c_ing}" if c_ing else "Menú semanal planificado"
        if entry.get("is_holiday"):
            c_desc += f"\\n🎉 Festivo: {entry.get('holiday_name', '')}"

        c_uid = f"menu-comida-{clean_date}@alvaro-ana-menu"
        ics_lines.extend([
            "BEGIN:VEVENT",
            f"UID:{c_uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;TZID=Europe/Madrid:{clean_date}T140000",
            f"DTEND;TZID=Europe/Madrid:{clean_date}T150000",
            f"SUMMARY:☀️ Comida: {c_name}",
            f"DESCRIPTION:{c_desc}",
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            "END:VEVENT"
        ])

        # 2. Evento Cena (21:00 a 22:00)
        cena = entry.get("cena", {})
        ce_name = cena.get("name", "Cena")
        ce_ing = cena.get("ingredients", "")
        ce_desc = f"Ingredientes: {ce_ing}" if ce_ing else "Menú semanal planificado"

        ce_uid = f"menu-cena-{clean_date}@alvaro-ana-menu"
        ics_lines.extend([
            "BEGIN:VEVENT",
            f"UID:{ce_uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;TZID=Europe/Madrid:{clean_date}T210000",
            f"DTEND;TZID=Europe/Madrid:{clean_date}T220000",
            f"SUMMARY:🌙 Cena: {ce_name}",
            f"DESCRIPTION:{ce_desc}",
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            "END:VEVENT"
        ])

    ics_lines.append("END:VCALENDAR")
    return "\r\n".join(ics_lines) + "\r\n"

def get_google_calendar_url(title: str, date_str: str, start_hour: int, duration_hours: int = 1, details: str = "") -> str:
    """
    Genera un enlace directo web para añadir un evento concreto a Google Calendar con 1 clic.
    """
    if not date_str:
        return ""
    clean_date = date_str.replace("-", "")
    start_time = f"{clean_date}T{start_hour:02d}0000"
    end_time = f"{clean_date}T{(start_hour + duration_hours):02d}0000"
    
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_time}/{end_time}",
        "ctz": "Europe/Madrid"
    }
    if details:
        params["details"] = details
        
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)

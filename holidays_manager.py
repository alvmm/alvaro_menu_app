from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

def get_easter_sunday(year: int) -> date:
    """Calcula el Domingo de Resurrección para cualquier año usando el algoritmo de Meeus/Jones/Butcher."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

def get_holidays_for_year(year: int) -> dict[date, str]:
    """
    Retorna los festivos nacionales y autonómicos oficiales de España / Comunidad de Madrid para un año dado.
    """
    holidays = {}

    # 1. Festivos con fecha fija
    fixed_holidays = {
        (1, 1): "Año Nuevo",
        (1, 6): "Epifanía del Señor (Reyes)",
        (5, 1): "Fiesta del Trabajo",
        (5, 2): "Fiesta de la Comunidad de Madrid",
        (5, 15): "San Isidro Labrador (Madrid)",
        (8, 15): "Asunción de la Virgen",
        (10, 12): "Fiesta Nacional de España (Día de la Hispanidad)",
        (11, 1): "Todos los Santos",
        (11, 9): "Virgen de la Almudena (Madrid)",
        (12, 6): "Día de la Constitución Española",
        (12, 8): "Inmaculada Concepción",
        (12, 25): "Natividad del Señor (Navidad)"
    }

    for (m, d), name in fixed_holidays.items():
        try:
            h_date = date(year, m, d)
            holidays[h_date] = name
            # Si cae en domingo y se traslada al lunes oficial
            if h_date.weekday() == 6:
                monday_transfer = h_date + timedelta(days=1)
                holidays[monday_transfer] = f"{name} (Traslado)"
        except ValueError:
            pass

    # 2. Festivos movibles (Semana Santa)
    try:
        easter = get_easter_sunday(year)
        jueves_santo = easter - timedelta(days=3)
        viernes_santo = easter - timedelta(days=2)
        holidays[jueves_santo] = "Jueves Santo"
        holidays[viernes_santo] = "Viernes Santo"
    except Exception as e:
        logger.warning(f"Error calculando Semana Santa para el año {year}: {e}")

    return holidays

def get_holiday_name(d: date) -> str | None:
    """Devuelve el nombre del festivo si la fecha dada es festivo en España/Madrid, o None si no lo es."""
    if not isinstance(d, date):
        return None
    year_holidays = get_holidays_for_year(d.year)
    return year_holidays.get(d)

def is_holiday(d: date) -> bool:
    """Comprueba si una fecha concreta es festivo."""
    return get_holiday_name(d) is not None

def is_festive_or_weekend(d: date) -> tuple[bool, str]:
    """
    Determina si un día es festivo o fin de semana:
    Retorna (is_festive: bool, description: str).
    """
    if not isinstance(d, date):
        return False, ""
    h_name = get_holiday_name(d)
    if h_name:
        return True, f"Festivo: {h_name}"
    if d.weekday() == 5:
        return True, "Sábado (Fin de semana)"
    if d.weekday() == 6:
        return True, "Domingo (Fin de semana)"
    return False, "Día laborable"

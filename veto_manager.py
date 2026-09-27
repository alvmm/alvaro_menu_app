import logging
from datetime import datetime, timedelta
from menu_generator import find_alternative_dish

logger = logging.getLogger(__name__)

VETO_LIMIT_PER_PERSON = 2

def get_veto_window_status(now: datetime = None) -> tuple[bool, str, datetime]:
    """
    Comprueba si la ventana de cambios y vetos está abierta:
    - Se abre el Sábado (con la ejecución/generación del menú semanal).
    - Se cierra el Domingo a las 16:00.
    Retorna: (is_open: bool, status_msg: str, target_datetime: datetime)
    """
    if now is None:
        now = datetime.now()

    weekday = now.weekday()  # Lunes=0, ..., Sábado=5, Domingo=6

    # Sábado: ventana abierta todo el día tras la ejecución del menú
    if weekday == 5:
        deadline = now.replace(hour=16, minute=0, second=0, microsecond=0) + timedelta(days=1)
        diff = deadline - now
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes = remainder // 60
        return True, f"Abierto hasta el domingo a las 16:00 (quedan {hours}h {minutes}min)", deadline

    # Domingo antes de las 16:00: ventana abierta
    elif weekday == 6 and now.hour < 16:
        deadline = now.replace(hour=16, minute=0, second=0, microsecond=0)
        diff = deadline - now
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes = remainder // 60
        return True, f"Abierto hasta hoy domingo a las 16:00 (quedan {hours}h {minutes}min)", deadline

    # Cerrado (Domingo desde las 16:00 o de Lunes a Viernes)
    else:
        days_ahead = (5 - weekday) % 7
        if days_ahead == 0 and weekday == 6:
            days_ahead = 6
        next_open = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        return False, "Cerrado (el menú ya está confirmado para la semana)", next_open

def normalize_user_name(user_name: str) -> str:
    """Normaliza el nombre del usuario a 'alvaro' o 'ana'."""
    u = str(user_name).strip().lower()
    if "álvaro" in u or "alvaro" in u:
        return "alvaro"
    return "ana"

def get_remaining_vetos(user_name: str, vetos_state: dict) -> int:
    """Retorna el número de vetos restantes para una persona."""
    norm_user = normalize_user_name(user_name)
    used_key = f"{norm_user}_used"
    # Compatibilidad con pareja_used si existe
    used = vetos_state.get(used_key, vetos_state.get("pareja_used", 0) if norm_user == "ana" else 0)
    return max(0, VETO_LIMIT_PER_PERSON - used)

def can_user_veto(user_name: str, vetos_state: dict) -> tuple[bool, int]:
    """Comprueba si el usuario tiene vetos disponibles."""
    remaining = get_remaining_vetos(user_name, vetos_state)
    return remaining > 0, remaining

def apply_veto(user_name: str, day_name: str, meal_type: str, current_menu: list, dishes_list: list, vetos_state: dict, check_window: bool = False, freezer_data: dict = None):
    """Aplica un veto a un plato concreto y lo sustituye por una alternativa sin cambiar el resto del menú."""
    if check_window:
        is_open, msg_window, _ = get_veto_window_status()
        if not is_open:
            return False, current_menu, vetos_state, "El plazo para realizar cambios y vetos finalizó el domingo a las 16:00. El menú ya está fijado.", None

    norm_user = normalize_user_name(user_name)
    display_name = "Álvaro" if norm_user == "alvaro" else "Ana"
    
    can_veto, remaining = can_user_veto(norm_user, vetos_state)
    if not can_veto:
        return False, current_menu, vetos_state, f"¡Aviso! {display_name} ya ha agotado sus 2 vetos de esta semana. No se permiten más cambios.", None

    # Buscar el día y el tipo de comida
    day_entry = None
    for entry in current_menu:
        if entry.get("day", "").lower() == day_name.lower():
            day_entry = entry
            break

    if not day_entry:
        return False, current_menu, vetos_state, f"No se encontró el día {day_name} en el menú.", None

    meal_key = "comida" if meal_type.lower() == "comida" else "cena"
    old_dish = day_entry.get(meal_key)
    old_dish_name = old_dish.get("name", "Plato anterior") if old_dish else "Ninguno"

    # Buscar alternativa válida respetando el congelador
    alternative_dish = find_alternative_dish(dishes_list, meal_key, current_menu, freezer_data=freezer_data)
    if not alternative_dish:
        return False, current_menu, vetos_state, "No hay platos alternativos disponibles en la base de datos.", None

    # Sustituir solo ese plato
    day_entry[meal_key] = alternative_dish

    # Actualizar estado de vetos
    updated_vetos = dict(vetos_state)
    used_key = f"{norm_user}_used"
    updated_vetos[used_key] = updated_vetos.get(used_key, 0) + 1
    if norm_user == "ana":
        updated_vetos["pareja_used"] = updated_vetos[used_key]
        updated_vetos["ana_used"] = updated_vetos[used_key]

    # Registrar en historial
    history = list(updated_vetos.get("history", []))
    history.append({
        "user": display_name,
        "day": day_name,
        "meal_type": meal_key.capitalize(),
        "old_dish": old_dish_name,
        "new_dish": alternative_dish["name"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    updated_vetos["history"] = history

    new_remaining = VETO_LIMIT_PER_PERSON - updated_vetos[used_key]
    msg = f"Veto aplicado por {display_name}. '{old_dish_name}' sustituido por '{alternative_dish['name']}'. (Vetos restantes para {display_name}: {new_remaining})"

    return True, current_menu, updated_vetos, msg, alternative_dish["name"]

def reset_weekly_vetos(vetos_state: dict) -> dict:
    """Reinicia los vetos de ambas personas a 0 (ejecutado automáticamente los sábados)."""
    updated_vetos = dict(vetos_state)
    updated_vetos["alvaro_used"] = 0
    updated_vetos["ana_used"] = 0
    updated_vetos["pareja_used"] = 0
    logger.info("Vetos semanales reiniciados correctamente (0/2 para Álvaro y Ana).")
    return updated_vetos

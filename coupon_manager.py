import uuid
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def create_coupon(user: str, title: str, restaurant: str, expiration_date: str, notes: str = "") -> dict:
    """Crea un nuevo diccionario de cupón/invitación."""
    # Asegurar formato de fecha válido YYYY-MM-DD
    formatted_date = expiration_date.strip()
    try:
        dt = datetime.strptime(formatted_date, "%Y-%m-%d")
        formatted_date = dt.strftime("%Y-%m-%d")
    except ValueError:
        pass  # Se mantiene la fecha ingresada si falla el parseo estricto

    return {
        "id": str(uuid.uuid4()),
        "user": "Álvaro" if "álvaro" in user.lower() or "alvaro" in user.lower() else "Ana",
        "title": title.strip(),
        "restaurant": restaurant.strip(),
        "expiration_date": formatted_date,
        "notes": notes.strip(),
        "status": "pendiente"  # 'pendiente' o 'usado'
    }

def add_coupon(coupons_list: list, coupon_data: dict) -> list:
    """Añade un nuevo cupón a la lista existente."""
    updated = list(coupons_list)
    updated.insert(0, coupon_data)
    return updated

def toggle_coupon_status(coupons_list: list, coupon_id: str) -> tuple[list, str]:
    """Alterna el estado de un cupón entre 'pendiente' y 'usado'."""
    updated = list(coupons_list)
    new_status = "pendiente"
    for c in updated:
        if c.get("id") == coupon_id:
            c["status"] = "usado" if c.get("status") == "pendiente" else "pendiente"
            new_status = c["status"]
            break
    return updated, new_status

def delete_coupon(coupons_list: list, coupon_id: str) -> list:
    """Elimina un cupón de la lista."""
    return [c for c in coupons_list if c.get("id") != coupon_id]

def get_coupons_by_user(coupons_list: list, user_filter: str = "todos") -> list:
    """Filtra cupones según el usuario ('Álvaro', 'Ana' o 'todos')."""
    if not user_filter or user_filter.lower() in ["todos", "all", "compartido"]:
        return coupons_list
    target_user = "Álvaro" if "álvaro" in user_filter.lower() or "alvaro" in user_filter.lower() else "Ana"
    return [c for c in coupons_list if c.get("user") == target_user]

def check_expiration_warning(expiration_date_str: str, threshold_days: int = 7) -> tuple[str, str, str]:
    """
    Evalúa la fecha de caducidad y retorna:
    - code: 'expired' | 'warning' | 'ok'
    - message: Texto explicativo
    - color_hex: Color para la interfaz UI
    """
    if not expiration_date_str:
        return "ok", "Sin fecha de caducidad", "#7F8C8D"
    
    try:
        exp_dt = datetime.strptime(expiration_date_str.strip(), "%Y-%m-%d").date()
        today = datetime.now().date()
        days_left = (exp_dt - today).days

        if days_left < 0:
            return "expired", f"¡CADUCADO hace {abs(days_left)} días!", "#E74C3C"
        elif days_left == 0:
            return "warning", "¡CADUCA HOY!", "#E67E22"
        elif days_left <= threshold_days:
            return "warning", f"¡Caduca pronto! ({days_left} días restantes)", "#F39C12"
        else:
            return "ok", f"Vence el {expiration_date_str} ({days_left} días)", "#2ECC71"
    except Exception as e:
        logger.warning(f"Error comprobando fecha de caducidad '{expiration_date_str}': {e}")
        return "ok", f"Vence: {expiration_date_str}", "#7F8C8D"

def get_expiring_coupons_alert(coupons_list: list, threshold_days: int = 7) -> list:
    """Retorna los cupones pendientes que están caducados o próximos a caducar."""
    alerts = []
    for c in coupons_list:
        if c.get("status") == "pendiente":
            code, msg, color = check_expiration_warning(c.get("expiration_date", ""), threshold_days)
            if code in ["expired", "warning"]:
                alerts.append({
                    "coupon": c,
                    "warning_code": code,
                    "message": msg,
                    "color": color
                })
    return alerts

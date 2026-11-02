import copy
import json
import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_DATA = {
    "settings": {
        "sheet_url": "",
        "sheet_gid_dishes": "83672031",
        "sheet_gid_freezer": "797240193",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "smtp_use_tls": True,
        "recipients": "",
        "auto_email_enabled": True,
        "calendar_ics_url": ""
    },
    "dishes": [],
    "current_menu": [],
    "vetos": {
        "alvaro_used": 0,
        "ana_used": 0,
        "pareja_used": 0,
        "history": []
    },
    "coupons": [
        {
            "id": "coupon-demo-1",
            "user": "Álvaro",
            "title": "Cena Romántica de Sushi",
            "restaurant": "Sushita Club",
            "expiration_date": "2026-10-15",
            "notes": "Cupón de cumpleaños para 2 personas.",
            "status": "pendiente"
        },
        {
            "id": "coupon-demo-2",
            "user": "Ana",
            "title": "2x1 en Hamburguesas Gourmet",
            "restaurant": "Goiko Grill",
            "expiration_date": "2026-10-02",
            "notes": "Válido para cenar en local de lunes a jueves.",
            "status": "pendiente"
        }
    ],
    "generation_meta": {
        "last_auto_gen_week": "",
        "manual_regens_this_week": 0,
        "last_manual_gen_date": ""
    },
    "freezer": {
        "items": {},
        "freezer_only_dishes": [
            "Lentejas", "Puchero", "Albóndigas", "Croquetas", "Garbanzos y calabacín al curry", "Muslitos guisados"
        ]
    },
    "shopping_checked": []
}

class StorageManager:
    """Maneja la persistencia de datos en un archivo JSON local en el dispositivo."""
    
    def __init__(self, filepath="menu_app_data.json"):
        self.filepath = filepath
        self.data = self.load_data()

    def load_data(self):
        if not os.path.exists(self.filepath):
            logger.info("Archivo de datos no encontrado. Creando valores por defecto.")
            default_copy = copy.deepcopy(DEFAULT_DATA)
            self.save_data(default_copy)
            return default_copy
        
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Asegurar claves faltantes por compatibilidad
                for key, val in DEFAULT_DATA.items():
                    if key not in data:
                        data[key] = copy.deepcopy(val)
                if "settings" in data and isinstance(data["settings"], dict):
                    for s_key, s_val in DEFAULT_DATA["settings"].items():
                        if s_key not in data["settings"]:
                            data["settings"][s_key] = s_val
                # Normalizar usuario legacy 'Pareja' -> 'Ana' en cupones
                for coupon in data.get("coupons", []):
                    if isinstance(coupon, dict) and str(coupon.get("user", "")).strip().lower() == "pareja":
                        coupon["user"] = "Ana"
                return data
        except Exception as e:
            logger.error(f"Error cargando archivo de datos JSON: {e}")
            return copy.deepcopy(DEFAULT_DATA)

    def save_data(self, data=None):
        if data is not None:
            self.data = data
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando datos JSON: {e}")
            return False

    def get_settings(self):
        """Devuelve la configuración guardada en el archivo JSON (sin inyectar secretos de entorno)."""
        return dict(self.data.get("settings", DEFAULT_DATA["settings"]))

    def get_effective_settings(self, st_secrets=None):
        """
        Devuelve una copia de la configuración combinando los valores guardados en JSON
        con los secretos de Streamlit (st.secrets) sin persistir los secretos en disco.
        """
        effective = self.get_settings()
        if st_secrets is not None:
            try:
                if "smtp" in st_secrets:
                    sec = st_secrets["smtp"]
                    if sec.get("user"):
                        effective["smtp_user"] = str(sec["user"])
                    if sec.get("password"):
                        effective["smtp_password"] = str(sec["password"])
                    if sec.get("recipients"):
                        effective["recipients"] = str(sec["recipients"])
                    if sec.get("host"):
                        effective["smtp_host"] = str(sec["host"])
                    if sec.get("port"):
                        effective["smtp_port"] = int(sec["port"])
                if "integrations" in st_secrets:
                    integ = st_secrets["integrations"]
                    if not effective.get("sheet_url") and integ.get("sheet_url"):
                        effective["sheet_url"] = str(integ["sheet_url"])
                    if not effective.get("sheet_gid_dishes") and integ.get("sheet_gid_dishes"):
                        effective["sheet_gid_dishes"] = str(integ["sheet_gid_dishes"])
                    if not effective.get("sheet_gid_freezer") and integ.get("sheet_gid_freezer"):
                        effective["sheet_gid_freezer"] = str(integ["sheet_gid_freezer"])
                    if not effective.get("calendar_ics_url") and integ.get("calendar_ics_url"):
                        effective["calendar_ics_url"] = str(integ["calendar_ics_url"])
            except Exception as e:
                logger.debug(f"No se pudieron leer secretos adicionales: {e}")
        return effective

    def update_settings(self, new_settings):
        self.data["settings"].update(new_settings)
        self.save_data()

    def get_current_menu(self):
        return self.data.get("current_menu", [])

    def save_current_menu(self, menu):
        self.data["current_menu"] = menu
        self.save_data()
        if "test" not in os.path.basename(self.filepath).lower():
            try:
                from calendar_exporter import save_menu_ics_file
                save_menu_ics_file(menu)
            except Exception as e:
                logger.warning(f"No se pudo actualizar el archivo ICS del calendario: {e}")


    def get_vetos(self):
        return self.data.get("vetos", DEFAULT_DATA["vetos"])

    def save_vetos(self, vetos_data):
        self.data["vetos"] = vetos_data
        self.save_data()

    def get_coupons(self):
        return self.data.get("coupons", [])

    def save_coupons(self, coupons_list):
        self.data["coupons"] = coupons_list
        self.save_data()

    def get_generation_meta(self):
        return self.data.get("generation_meta", DEFAULT_DATA["generation_meta"])

    def save_generation_meta(self, meta_data):
        self.data["generation_meta"] = meta_data
        self.save_data()

    def get_dishes(self):
        return self.data.get("dishes", [])

    def save_dishes(self, dishes_list):
        self.data["dishes"] = dishes_list
        self.save_data()

    def get_freezer(self):
        return self.data.get("freezer", DEFAULT_DATA["freezer"])

    def save_freezer(self, freezer_data):
        self.data["freezer"] = freezer_data
        self.save_data()

    def get_shopping_checked(self) -> list[str]:
        return list(self.data.get("shopping_checked", []))

    def save_shopping_checked(self, checked_list: list[str]):
        self.data["shopping_checked"] = list(checked_list)
        self.save_data()


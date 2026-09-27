import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_DATA = {
    "settings": {
        "sheet_url": "https://docs.google.com/spreadsheets/d/163wHVPAMQbmkS1PqNZvLc-jDLzb2F9iiYF0FhM3jaU0/edit?gid=83672031#gid=83672031",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "alv.mmartin@gmail.com",
        "smtp_password": "",
        "smtp_use_tls": True,
        "recipients": "alv.mmartin@gmail.com, absaladomoreno@gmail.com",
        "auto_email_enabled": True
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
    }
}

class StorageManager:
    """Maneja la persistencia de datos en un archivo JSON local en el dispositivo."""
    
    def __init__(self, filepath="menu_app_data.json"):
        self.filepath = filepath
        self.data = self.load_data()

    def load_data(self):
        if not os.path.exists(self.filepath):
            logger.info("Archivo de datos no encontrado. Creando valores por defecto.")
            self.save_data(DEFAULT_DATA)
            return DEFAULT_DATA
        
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Asegurar claves faltantes por compatibilidad
                for key, val in DEFAULT_DATA.items():
                    if key not in data:
                        data[key] = val
                return data
        except Exception as e:
            logger.error(f"Error cargando archivo de datos JSON: {e}")
            return DEFAULT_DATA

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
        return self.data.get("settings", DEFAULT_DATA["settings"])

    def update_settings(self, new_settings):
        self.data["settings"].update(new_settings)
        self.save_data()

    def get_current_menu(self):
        return self.data.get("current_menu", [])

    def save_current_menu(self, menu):
        self.data["current_menu"] = menu
        self.save_data()

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

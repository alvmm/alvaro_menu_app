import logging
from datetime import datetime
from kivy.clock import Clock

from csv_loader import fetch_dishes_from_csv
from menu_generator import generate_weekly_menu
from veto_manager import reset_weekly_vetos
from emailer import send_weekly_menu_email

logger = logging.getLogger(__name__)

class WeeklyScheduler:
    """Gestiona las tareas programadas automáticamente cada sábado."""

    def __init__(self, storage_manager, on_menu_updated_callback=None):
        self.storage = storage_manager
        self.on_menu_updated_callback = on_menu_updated_callback
        self._event = None

    def start(self, interval_seconds=300):
        """Inicia la comprobación periódica en segundo plano usando Kivy Clock."""
        if self._event is None:
            # Comprobación inicial inmediata y luego cada `interval_seconds` (ej. 5 minutos)
            self.check_saturday_trigger(0)
            self._event = Clock.schedule_interval(self.check_saturday_trigger, interval_seconds)
            logger.info("Scheduler de menú semanal iniciado correctamente.")

    def stop(self):
        """Detiene la comprobación del scheduler."""
        if self._event:
            self._event.cancel()
            self._event = None
            logger.info("Scheduler detenido.")

    def check_saturday_trigger(self, dt):
        """Comprueba si es sábado y si el menú de esta semana ya ha sido generado automáticamente."""
        now = datetime.now()
        # En Python, el sábado es el día 5 (Lunes=0, ..., Sábado=5, Domingo=6)
        is_saturday = (now.weekday() == 5)
        
        # Identificador único de semana (ej: '2026-W39')
        current_week_str = now.strftime("%Y-W%U")

        meta = self.storage.get_generation_meta()
        last_gen_week = meta.get("last_auto_gen_week", "")

        if is_saturday and (last_gen_week != current_week_str):
            logger.info(f"¡Hoy es sábado! Ejecutando generación automática del menú semanal para la semana {current_week_str}.")
            self.execute_saturday_routine(current_week_str)

    def execute_saturday_routine(self, week_str):
        """Ejecuta la rutina completa de cada sábado: CSV -> Menú -> Reset Vetos -> Guardar -> Email."""
        settings = self.storage.get_settings()
        sheet_url = settings.get("sheet_url", "")

        # 1. Cargar platos desde CSV
        dishes, _ = fetch_dishes_from_csv(sheet_url)
        self.storage.save_dishes(dishes)

        # 2. Generar nuevo menú
        new_menu = generate_weekly_menu(dishes)
        self.storage.save_current_menu(new_menu)

        # 3. Reiniciar vetos semanales (0/2 para Álvaro y Pareja)
        vetos = self.storage.get_vetos()
        updated_vetos = reset_weekly_vetos(vetos)
        self.storage.save_vetos(updated_vetos)

        # 4. Actualizar metadata de generación
        meta = self.storage.get_generation_meta()
        meta["last_auto_gen_week"] = week_str
        meta["manual_regens_this_week"] = 0
        meta["last_auto_gen_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.storage.save_generation_meta(meta)

        # 5. Enviar correo automático si está activado
        if settings.get("auto_email_enabled", True):
            success, msg = send_weekly_menu_email(settings, new_menu, is_test=False)
            logger.info(f"Resultado envío automático de correo de sábado: {msg}")

        # 6. Notificar a la interfaz UI si hay callback registrado
        if self.on_menu_updated_callback:
            try:
                self.on_menu_updated_callback(new_menu)
            except Exception as e:
                logger.error(f"Error en callback UI tras generación de sábado: {e}")

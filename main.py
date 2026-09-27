import os
import sys
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.properties import StringProperty, ObjectProperty, NumericProperty

# Importar módulos propios de la arquitectura
from storage_manager import StorageManager
from csv_loader import fetch_dishes_from_csv, get_sample_dishes
from menu_generator import generate_weekly_menu, regenerate_menu_manually
from veto_manager import apply_veto, can_user_veto, get_remaining_vetos, reset_weekly_vetos
from coupon_manager import (
    create_coupon, add_coupon, toggle_coupon_status, delete_coupon, 
    get_coupons_by_user, check_expiration_warning, get_expiring_coupons_alert
)
from emailer import send_weekly_menu_email
from scheduler import WeeklyScheduler


# --- COMPONENTE WIDGET DE TARJETA DÍA ---
class DayMenuCard(BoxLayout):
    day_name = StringProperty('Lunes')
    comida_name = StringProperty('Comida')
    comida_ing = StringProperty('')
    cena_name = StringProperty('Cena')
    cena_ing = StringProperty('')


# --- PANTALLAS ---
class HomeScreen(Screen):
    def on_enter(self):
        app = App.get_running_app()
        vetos = app.storage.get_vetos()
        
        # Actualizar vetos en la vista de inicio
        alvaro_used = vetos.get("alvaro_used", 0)
        pareja_used = vetos.get("pareja_used", 0)
        
        self.ids.lbl_alvaro_vetos.text = f"👤 Álvaro: {alvaro_used}/2 usados"
        self.ids.lbl_pareja_vetos.text = f"👩‍🦰 Pareja: {pareja_used}/2 usados"

        # Comprobar cupones próximos a caducar
        coupons = app.storage.get_coupons()
        alerts = get_expiring_coupons_alert(coupons, threshold_days=7)
        
        if alerts:
            first = alerts[0]
            c = first["coupon"]
            self.ids.lbl_coupon_alert_title.text = f"🎟️ ¡Atención! {first['message']}"
            self.ids.lbl_coupon_alert_desc.text = f"'{c.get('title')}' de {c.get('user')} en {c.get('restaurant')} (Vence: {c.get('expiration_date')})"
        else:
            self.ids.lbl_coupon_alert_title.text = "🎟️ Invitaciones y Cupones"
            self.ids.lbl_coupon_alert_desc.text = "Sin cupones próximos a caducar esta semana."


class MenuScreen(Screen):
    def on_enter(self):
        self.refresh_calendar()

    def refresh_calendar(self):
        app = App.get_running_app()
        current_menu = app.storage.get_current_menu()
        meta = app.storage.get_generation_meta()

        # Si el menú está vacío, generar uno inicial
        if not current_menu:
            dishes = app.storage.get_dishes()
            if not dishes:
                sheet_url = app.storage.get_settings().get("sheet_url", "")
                dishes, _ = fetch_dishes_from_csv(sheet_url)
                app.storage.save_dishes(dishes)
            current_menu = generate_weekly_menu(dishes)
            app.storage.save_current_menu(current_menu)

        # Actualizar texto del botón de regeneración manual
        manual_used = meta.get("manual_regens_this_week", 0)
        rem = max(0, 1 - manual_used)
        self.ids.btn_regenerate_menu.text = f"🔄 Regenerar Menú ({rem}/1 disp.)"
        if rem == 0:
            self.ids.btn_regenerate_menu.background_color = (0.6, 0.6, 0.6, 1)
        else:
            self.ids.btn_regenerate_menu.background_color = (0.12, 0.45, 0.78, 1)

        # Poblar el contenedor del calendario semanal
        container = self.ids.calendar_container
        container.clear_widgets()

        for entry in current_menu:
            day = entry.get("day", "")
            comida = entry.get("comida", {})
            cena = entry.get("cena", {})

            card = DayMenuCard(
                day_name=day,
                comida_name=comida.get("name", "Sin asignar"),
                comida_ing=comida.get("ingredients", ""),
                cena_name=cena.get("name", "Sin asignar"),
                cena_ing=cena.get("ingredients", "")
            )
            container.add_widget(card)

    def on_click_regenerate(self):
        app = App.get_running_app()
        meta = app.storage.get_generation_meta()
        dishes = app.storage.get_dishes()
        
        if not dishes:
            dishes = get_sample_dishes()

        success, new_menu, new_meta, msg = regenerate_menu_manually(dishes, meta)

        if success:
            app.storage.save_current_menu(new_menu)
            app.storage.save_generation_meta(new_meta)
            self.refresh_calendar()
            app.show_popup("Menú Regenerado", "Se ha generado un nuevo menú semanal completo para Álvaro y su pareja.")
        else:
            app.show_popup("Límite Alcanzado", msg)

    def on_click_send_email(self):
        app = App.get_running_app()
        settings = app.storage.get_settings()
        menu = app.storage.get_current_menu()

        success, msg = send_weekly_menu_email(settings, menu, is_test=False)
        if success:
            app.show_popup("Email Enviado", msg)
        else:
            app.show_popup("Error de Envío", msg)


class CouponsScreen(Screen):
    current_filter = StringProperty('todos')

    def on_enter(self):
        self.refresh_coupons_list()

    def set_filter(self, filter_name):
        self.current_filter = filter_name
        self.ids.btn_filter_todos.background_color = (0.12, 0.45, 0.78, 1) if filter_name == 'todos' else (0.5, 0.55, 0.6, 1)
        self.ids.btn_filter_alvaro.background_color = (0.12, 0.45, 0.78, 1) if filter_name == 'Álvaro' else (0.5, 0.55, 0.6, 1)
        self.ids.btn_filter_pareja.background_color = (0.12, 0.45, 0.78, 1) if filter_name == 'Pareja' else (0.5, 0.55, 0.6, 1)
        self.refresh_coupons_list()

    def refresh_coupons_list(self):
        app = App.get_running_app()
        coupons = app.storage.get_coupons()
        filtered = get_coupons_by_user(coupons, self.current_filter)

        container = self.ids.coupons_container
        container.clear_widgets()

        if not filtered:
            lbl = Label(
                text="No hay cupones registrados en esta categoría.",
                size_hint_y=None, height='40dp', color=(0.5, 0.5, 0.5, 1)
            )
            container.add_widget(lbl)
            return

        for coupon in filtered:
            card = self.create_coupon_card(coupon)
            container.add_widget(card)

    def create_coupon_card(self, coupon):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height='140dp',
            padding='12dp',
            spacing='6dp'
        )
        # Estilo de tarjeta según estado de caducidad
        code, status_msg, color_hex = check_expiration_warning(coupon.get("expiration_date", ""))
        
        # Background card
        with card.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[8,])

        # Fila Superior: Título + Badge Usuario
        row1 = BoxLayout(size_hint_y=None, height='24dp')
        title_lbl = Label(
            text=f"🎟️ {coupon.get('title')}", font_size='15sp', bold=True,
            color=(0.15, 0.2, 0.25, 1), text_size=(None, None), halign='left'
        )
        user_badge = Label(
            text=f"[{coupon.get('user')}]", font_size='12sp', bold=True,
            color=(0.12, 0.45, 0.78, 1) if coupon.get('user') == 'Álvaro' else (0.8, 0.2, 0.5, 1),
            size_hint_x=None, width='80dp'
        )
        row1.add_widget(title_lbl)
        row1.add_widget(user_badge)

        # Fila 2: Restaurante y Caducidad
        row2 = BoxLayout(size_hint_y=None, height='20dp')
        rest_lbl = Label(
            text=f"📍 {coupon.get('restaurant')}", font_size='12sp',
            color=(0.3, 0.35, 0.4, 1), text_size=(None, None), halign='left'
        )
        exp_lbl = Label(
            text=status_msg, font_size='11sp', bold=True,
            color=(0.85, 0.25, 0.2, 1) if code in ['expired', 'warning'] else (0.2, 0.6, 0.3, 1),
            size_hint_x=None, width='180dp'
        )
        row2.add_widget(rest_lbl)
        row2.add_widget(exp_lbl)

        # Fila 3: Notas
        notes_lbl = Label(
            text=f"📝 {coupon.get('notes')}" if coupon.get('notes') else "Sin notas adicionales.",
            font_size='11sp', color=(0.5, 0.55, 0.6, 1), size_hint_y=None, height='18dp',
            text_size=(None, None), halign='left'
        )

        # Fila 4: Botones Acción
        row4 = BoxLayout(size_hint_y=None, height='32dp', spacing='10dp')
        is_used = coupon.get("status") == "usado"
        btn_toggle = Button(
            text="✅ Marcado como Usado" if is_used else "⏳ Estado: Pendiente",
            font_size='12sp', bold=True,
            background_normal='',
            background_color=(0.5, 0.5, 0.5, 1) if is_used else (0.2, 0.65, 0.45, 1)
        )
        btn_toggle.bind(on_release=lambda instance, cid=coupon.get("id"): self.toggle_coupon(cid))

        btn_delete = Button(
            text="🗑️ Eliminar", size_hint_x=None, width='90dp',
            font_size='12sp', background_normal='', background_color=(0.8, 0.2, 0.2, 1)
        )
        btn_delete.bind(on_release=lambda instance, cid=coupon.get("id"): self.remove_coupon(cid))

        row4.add_widget(btn_toggle)
        row4.add_widget(btn_delete)

        card.add_widget(row1)
        card.add_widget(row2)
        card.add_widget(notes_lbl)
        card.add_widget(row4)

        return card

    def toggle_coupon(self, coupon_id):
        app = App.get_running_app()
        coupons = app.storage.get_coupons()
        updated, _ = toggle_coupon_status(coupons, coupon_id)
        app.storage.save_coupons(updated)
        self.refresh_coupons_list()

    def remove_coupon(self, coupon_id):
        app = App.get_running_app()
        coupons = app.storage.get_coupons()
        updated = delete_coupon(coupons, coupon_id)
        app.storage.save_coupons(updated)
        self.refresh_coupons_list()

    def open_add_coupon_modal(self):
        content = BoxLayout(orientation='vertical', padding='12dp', spacing='10dp')
        
        # Campo Usuario
        row_user = BoxLayout(size_hint_y=None, height='40dp', spacing='10dp')
        row_user.add_widget(Label(text="¿De quién es el cupón?:", size_hint_x=0.4))
        sp_user = Spinner(text='Álvaro', values=('Álvaro', 'Pareja'), size_hint_x=0.6)
        row_user.add_widget(sp_user)
        
        # Campo Título
        txt_title = TextInput(hint_text="Nombre del cupón (ej: Cena 2x1)", multiline=False, size_hint_y=None, height='40dp')
        
        # Campo Restaurante
        txt_rest = TextInput(hint_text="Restaurante / Establecimiento", multiline=False, size_hint_y=None, height='40dp')
        
        # Campo Fecha Límite
        default_exp = datetime.now().strftime("%Y-%m-%d")
        txt_date = TextInput(text=default_exp, hint_text="Fecha Límite (AAAA-MM-DD)", multiline=False, size_hint_y=None, height='40dp')
        
        # Campo Notas
        txt_notes = TextInput(hint_text="Notas o condiciones del cupón", multiline=False, size_hint_y=None, height='40dp')

        content.add_widget(row_user)
        content.add_widget(txt_title)
        content.add_widget(txt_rest)
        content.add_widget(txt_date)
        content.add_widget(txt_notes)

        popup = Popup(
            title="➕ Registrar Nueva Invitación / Cupón",
            content=content,
            size_hint=(0.9, 0.65)
        )

        btn_save = Button(text="💾 Guardar Cupón", size_hint_y=None, height='44dp', background_normal='', background_color=(0.12, 0.45, 0.78, 1))
        
        def save_and_close(instance):
            if not txt_title.text.strip():
                return
            new_c = create_coupon(
                user=sp_user.text,
                title=txt_title.text,
                restaurant=txt_rest.text,
                expiration_date=txt_date.text,
                notes=txt_notes.text
            )
            app = App.get_running_app()
            updated = add_coupon(app.storage.get_coupons(), new_c)
            app.storage.save_coupons(updated)
            popup.dismiss()
            self.refresh_coupons_list()

        btn_save.bind(on_release=save_and_close)
        content.add_widget(btn_save)
        popup.open()


class SettingsScreen(Screen):
    def on_enter(self):
        app = App.get_running_app()
        s = app.storage.get_settings()
        
        self.ids.txt_sheet_url.text = s.get("sheet_url", "")
        self.ids.txt_smtp_host.text = s.get("smtp_host", "")
        self.ids.txt_smtp_port.text = str(s.get("smtp_port", 587))
        self.ids.txt_smtp_user.text = s.get("smtp_user", "")
        self.ids.txt_smtp_password.text = s.get("smtp_password", "")
        self.ids.txt_recipients.text = s.get("recipients", "")

    def test_and_save_sheet_url(self):
        url = self.ids.txt_sheet_url.text.strip()
        app = App.get_running_app()
        
        dishes, status_msg = fetch_dishes_from_csv(url)
        app.storage.save_dishes(dishes)
        
        s = app.storage.get_settings()
        s["sheet_url"] = url
        app.storage.update_settings(s)

        app.show_popup("Google Sheet CSV", status_msg)

    def save_smtp_settings(self):
        app = App.get_running_app()
        s = app.storage.get_settings()
        
        s["smtp_host"] = self.ids.txt_smtp_host.text.strip()
        try:
            s["smtp_port"] = int(self.ids.txt_smtp_port.text.strip())
        except ValueError:
            s["smtp_port"] = 587
        s["smtp_user"] = self.ids.txt_smtp_user.text.strip()
        s["smtp_password"] = self.ids.txt_smtp_password.text.strip()
        s["recipients"] = self.ids.txt_recipients.text.strip()

        app.storage.update_settings(s)
        app.show_popup("Ajustes Guardados", "Los datos del servidor SMTP se han guardado correctamente.")

    def send_test_email(self):
        app = App.get_running_app()
        s = app.storage.get_settings()
        menu = app.storage.get_current_menu()
        
        success, msg = send_weekly_menu_email(s, menu, is_test=True)
        if success:
            app.show_popup("Prueba SMTP Exitosa", msg)
        else:
            app.show_popup("Error SMTP", msg)

    def reset_vetos_manually(self):
        app = App.get_running_app()
        vetos = app.storage.get_vetos()
        updated = reset_weekly_vetos(vetos)
        app.storage.save_vetos(updated)
        app.show_popup("Vetos Reiniciados", "Los vetos de Álvaro y Pareja se han reiniciado a 0/2.")


class RootScreenManager(ScreenManager):
    pass


# --- APLICACIÓN PRINCIPAL KIVY ---
class AlvaroMenuApp(App):
    storage = ObjectProperty(None)
    scheduler = ObjectProperty(None)

    def build(self):
        self.title = "Menú Álvaro & Pareja"
        
        # Inicializar almacenamiento persistente JSON
        self.storage = StorageManager()

        # Cargar KV
        kv_path = os.path.join(os.path.dirname(__file__), "alvaromenu.kv")
        if os.path.exists(kv_path):
            Builder.load_file(kv_path)

        # Iniciar Scheduler de Sábado en segundo plano
        self.scheduler = WeeklyScheduler(self.storage, on_menu_updated_callback=self.on_saturday_menu_auto_updated)
        self.scheduler.start(interval_seconds=300)

        sm = RootScreenManager()
        return sm

    def go_to_screen(self, screen_name):
        if self.root:
            self.root.current = screen_name

    def on_saturday_menu_auto_updated(self, new_menu):
        """Callback ejecutado cuando el scheduler de sábado renueva el menú automáticamente."""
        logger.info("Scheduler notificó renovación de menú. Actualizando pantallas UI.")
        if self.root and self.root.has_screen("menu"):
            menu_screen = self.root.get_screen("menu")
            menu_screen.refresh_calendar()

    def open_veto_dialog(self, day_name, meal_type):
        """Abre un diálogo modal para seleccionar quién aplica el veto a un plato concreto."""
        vetos = self.storage.get_vetos()
        rem_alvaro = get_remaining_vetos("alvaro", vetos)
        rem_pareja = get_remaining_vetos("pareja", vetos)

        content = BoxLayout(orientation='vertical', padding='14dp', spacing='12dp')
        
        lbl_info = Label(
            text=f"🛑 ¿Quién desea vetar la {meal_type} del {day_name}?\nSe buscará una alternativa válida sin regenerar el menú completo.",
            font_size='13sp', halign='center', valign='middle'
        )
        content.add_widget(lbl_info)

        btn_alvaro = Button(
            text=f"👤 Álvaro ({rem_alvaro}/2 vetos restantes)",
            size_hint_y=None, height='48dp',
            font_size='14sp', bold=True,
            background_normal='',
            background_color=(0.12, 0.45, 0.78, 1) if rem_alvaro > 0 else (0.6, 0.6, 0.6, 1)
        )

        btn_pareja = Button(
            text=f"👩‍🦰 Pareja ({rem_pareja}/2 vetos restantes)",
            size_hint_y=None, height='48dp',
            font_size='14sp', bold=True,
            background_normal='',
            background_color=(0.8, 0.2, 0.5, 1) if rem_pareja > 0 else (0.6, 0.6, 0.6, 1)
        )

        content.add_widget(btn_alvaro)
        content.add_widget(btn_pareja)

        popup = Popup(
            title=f"🛑 Sistema de Vetos - {day_name} ({meal_type})",
            content=content,
            size_hint=(0.88, 0.45)
        )

        def handle_veto(user_name):
            popup.dismiss()
            menu = self.storage.get_current_menu()
            dishes = self.storage.get_dishes()
            if not dishes:
                dishes = get_sample_dishes()

            current_vetos = self.storage.get_vetos()
            success, updated_menu, updated_vetos, msg, new_dish_name = apply_veto(
                user_name, day_name, meal_type, menu, dishes, current_vetos
            )

            if success:
                self.storage.save_current_menu(updated_menu)
                self.storage.save_vetos(updated_vetos)
                
                # Refrescar pantalla del menú
                if self.root and self.root.has_screen("menu"):
                    self.root.get_screen("menu").refresh_calendar()
                
                self.show_popup("Veto Aplicado", msg)
            else:
                self.show_popup("Veto Bloqueado", msg)

        btn_alvaro.bind(on_release=lambda x: handle_veto("Álvaro"))
        btn_pareja.bind(on_release=lambda x: handle_veto("Pareja"))

        popup.open()

    def show_popup(self, title, message):
        """Muestra una ventana emergente / diálogo informativo genérico."""
        content = BoxLayout(orientation='vertical', padding='14dp', spacing='12dp')
        lbl = Label(text=message, font_size='13sp', halign='center', valign='middle')
        content.add_widget(lbl)
        
        btn_close = Button(
            text="Entendido", size_hint_y=None, height='42dp',
            font_size='14sp', bold=True,
            background_normal='', background_color=(0.12, 0.45, 0.78, 1)
        )
        content.add_widget(btn_close)

        popup = Popup(title=title, content=content, size_hint=(0.85, 0.35))
        btn_close.bind(on_release=popup.dismiss)
        popup.open()

    def on_stop(self):
        """Detener scheduler al cerrar la app."""
        if self.scheduler:
            self.scheduler.stop()


if __name__ == "__main__":
    AlvaroMenuApp().run()

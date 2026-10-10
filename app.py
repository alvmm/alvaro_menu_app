import streamlit as st
from datetime import datetime, date, timedelta
import pandas as pd
import logging

from storage_manager import StorageManager
from menu_generator import (
    generate_weekly_menu, regenerate_menu_manually, 
    get_current_menu_cycle_key, DAYS_OF_WEEK
)
from veto_manager import (
    apply_veto, reset_weekly_vetos, get_remaining_vetos, 
    get_veto_window_status, VETO_LIMIT_PER_PERSON
)
from coupon_manager import (
    create_coupon, add_coupon, toggle_coupon_status, delete_coupon,
    get_coupons_by_user, get_expiring_coupons_alert, check_expiration_warning
)
from emailer import send_weekly_menu_email, generate_menu_html
from csv_loader import fetch_dishes_from_csv, fetch_freezer_from_csv, get_sample_dishes
from calendar_loader import fetch_calendar_events, get_events_for_menu_week
from holidays_manager import get_holiday_name
from calendar_exporter import generate_menu_ics, get_google_calendar_url

# Configuración de página responsive y moderna
st.set_page_config(
    page_title="Menú Semanal - Álvaro & Ana",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

logger = logging.getLogger(__name__)

def check_and_run_weekly_auto_generation(storage_instance):
    """
    Comprueba si el ciclo semanal actual (iniciado en sábado) ya tiene su menú generado.
    Si no coincide con 'last_auto_gen_week', ejecuta la rutina automática semanal:
    1. Sincroniza platos y congelador desde Google Sheets (si hay conexión y URL configurada).
    2. Genera un menú semanal equilibrado filtrando según el congelador.
    3. Reinicia los vetos de la semana (0/2 para Álvaro y Ana).
    4. Reinicia las regeneraciones manuales (0/1 usadas).
    5. Actualiza generation_meta con la clave de ciclo y fecha.
    6. Guarda todo en storage.
    7. Envía el email si auto_email_enabled está activo y configurado.
    Retorna: (was_generated: bool, cycle_desc: str)
    """
    now = datetime.now()
    cycle_key, cycle_desc = get_current_menu_cycle_key(now)
    
    meta_data = storage_instance.get_generation_meta()
    last_cycle = meta_data.get("last_auto_gen_week", "")
    current_menu_data = storage_instance.get_current_menu()
    
    # Comprobar si toca generar (ciclo distinto o menú no existente)
    needs_generation = (last_cycle != cycle_key) or (not current_menu_data)
    
    if not needs_generation:
        return False, cycle_desc

    logger.info(f"Nuevo ciclo detectado ({cycle_key}). Generando menú semanal automáticamente...")
    settings_data = storage_instance.get_settings()
    sheet_url = settings_data.get("sheet_url", "")
    gid_dishes = settings_data.get("sheet_gid_dishes", "83672031")
    gid_freezer = settings_data.get("sheet_gid_freezer", "797240193")
    
    # 1. Intentar actualizar desde Google Sheets si está configurado
    dishes_list = storage_instance.get_dishes()
    freezer_info = storage_instance.get_freezer()
    if sheet_url:
        try:
            loaded_dishes, _ = fetch_dishes_from_csv(sheet_url, gid=gid_dishes)
            if loaded_dishes:
                dishes_list = loaded_dishes
                storage_instance.save_dishes(dishes_list)
            loaded_freezer, _ = fetch_freezer_from_csv(sheet_url, gid=gid_freezer)
            if loaded_freezer:
                freezer_info["items"] = loaded_freezer
                storage_instance.save_freezer(freezer_info)
        except Exception as e:
            logger.warning(f"No se pudo sincronizar Google Sheets en auto-generación: {e}")

    if not dishes_list:
        dishes_list = get_sample_dishes()
        storage_instance.save_dishes(dishes_list)

    # 2. Generar nuevo menú semanal respetando el congelador
    new_menu = generate_weekly_menu(dishes_list, freezer_data=freezer_info)
    storage_instance.save_current_menu(new_menu)

    # 3. Reiniciar vetos semanales a 0 (2 disponibles para Álvaro y 2 para Ana)
    current_vetos = storage_instance.get_vetos()
    updated_vetos = reset_weekly_vetos(current_vetos)
    storage_instance.save_vetos(updated_vetos)

    # 4. Actualizar metadata de generación
    meta_data["last_auto_gen_week"] = cycle_key
    meta_data["manual_regens_this_week"] = 0
    meta_data["last_auto_gen_date"] = now.strftime("%Y-%m-%d %H:%M")
    storage_instance.save_generation_meta(meta_data)

    # 5. Enviar email automático si está activado y con contraseña configurada
    if settings_data.get("auto_email_enabled", True) and settings_data.get("smtp_password"):
        try:
            send_weekly_menu_email(settings_data, new_menu, is_test=False)
        except Exception as e:
            logger.error(f"Error enviando email semanal automático: {e}")

    return True, cycle_desc

# Inicializar StorageManager (siempre sincronizado con el archivo JSON)
storage = StorageManager()

# Comprobar y ejecutar generación automática semanal si ha cambiado el ciclo
auto_generated_now, cycle_desc = check_and_run_weekly_auto_generation(storage)

# Cargar datos actuales tras la comprobación del ciclo
dishes = storage.get_dishes()
if not dishes:
    dishes = get_sample_dishes()
    storage.save_dishes(dishes)

current_menu = storage.get_current_menu()
if not current_menu:
    current_menu = generate_weekly_menu(dishes, freezer_data=storage.get_freezer())
    storage.save_current_menu(current_menu)

vetos_state = storage.get_vetos()
settings = storage.get_settings()
coupons = storage.get_coupons()
meta = storage.get_generation_meta()
freezer_data = storage.get_freezer()

# Cargar eventos del calendario AyA si está configurado
calendar_ics_url = settings.get("calendar_ics_url", "")
cal_week_map = {}
if calendar_ics_url:
    try:
        raw_cal_events = fetch_calendar_events(calendar_ics_url)
        cal_week_map = get_events_for_menu_week(raw_cal_events)
    except Exception as e:
        logger.warning(f"Error cargando eventos del calendario AyA: {e}")

# Soporte para secretos seguros en Streamlit Cloud (st.secrets)
try:
    if hasattr(st, "secrets") and "smtp" in st.secrets:
        sec = st.secrets["smtp"]
        if "user" in sec: settings["smtp_user"] = str(sec["user"])
        if "password" in sec: settings["smtp_password"] = str(sec["password"])
        if "recipients" in sec: settings["recipients"] = str(sec["recipients"])
        if "host" in sec: settings["smtp_host"] = str(sec["host"])
        if "port" in sec: settings["smtp_port"] = int(sec["port"])
except Exception:
    pass

# --- CSS Personalizado para un diseño limpio y moderno ---
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 24px;
        border-radius: 16px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 14px;
        text-align: center;
    }
    .dish-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
    }
    .dish-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 4px;
    }
    .dish-ing {
        font-size: 0.85rem;
        color: #64748B;
        margin-bottom: 10px;
    }
    .badge-comida {
        background-color: #FEF3C7;
        color: #B45309;
        font-weight: 600;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 9999px;
    }
    .badge-cena {
        background-color: #E0E7FF;
        color: #4338CA;
        font-weight: 600;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 9999px;
    }
    .badge-alvaro {
        background-color: #DBEAFE;
        color: #1E40AF;
        padding: 2px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-ana {
        background-color: #FCE7F3;
        color: #9D174D;
        padding: 2px 8px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-freezer {
        background-color: #E0F2FE;
        color: #0369A1;
        font-weight: 600;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 9999px;
        margin-left: 6px;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER PRINCIPAL ---
alvaro_vetos_left = get_remaining_vetos("alvaro", vetos_state)
ana_vetos_left = get_remaining_vetos("ana", vetos_state)
expiring_coupons = get_expiring_coupons_alert(coupons)

manual_used = meta.get("manual_regens_this_week", 0)
can_manual_regen = (manual_used < 1)
manual_regens_left = max(0, 1 - manual_used)

st.markdown(f"""
<div class="main-header">
    <h1 style="margin: 0; font-size: 1.8rem;">🍽️ Planificador de Menú Semanal</h1>
    <p style="margin: 4px 0 0 0; opacity: 0.9; font-size: 0.95rem;">Aplicación privada para Álvaro & Ana • <strong>{cycle_desc}</strong></p>
</div>
""", unsafe_allow_html=True)

# Métricas superiores en 5 columnas
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("👨 Vetos Álvaro", f"{alvaro_vetos_left} / {VETO_LIMIT_PER_PERSON} disp.")
with col2:
    st.metric("👩 Vetos Ana", f"{ana_vetos_left} / {VETO_LIMIT_PER_PERSON} disp.")
with col3:
    st.metric("🎲 Regen. Manual", f"{manual_regens_left} / 1 disp.", help="Límite estricto: solo 1 regeneración manual por semana. Si se usa, queda bloqueada.")
with col4:
    total_frozen = len([k for k, v in freezer_data.get("items", {}).items() if v is True or str(v).lower() in ['si', 'sí', 'true', '1']])
    st.metric("🧊 Congelador", f"{total_frozen} disp.")
with col5:
    pending_coupons = len([c for c in coupons if c.get("status") == "pendiente"])
    st.metric("🎟️ Cupones pendientes", pending_coupons, delta=f"{len(expiring_coupons)} por caducar" if expiring_coupons else None, delta_color="inverse")

# Alerta de notificación automática de sábado si acaba de generarse
if auto_generated_now:
    st.toast(f"✨ ¡Menú generado automáticamente para {cycle_desc}!", icon="🍽️")

# Alerta de cupones por caducar si los hay
if expiring_coupons:
    with st.container():
        st.warning(f"⚠️ **Atención:** Tienes **{len(expiring_coupons)} cupón(es)** a punto de caducar o caducados. Revisa la pestaña de Cupones.")

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("⚡ Acciones Rápidas")
    
    # Botón de Regeneración Manual (Límite estricto de 1 por semana)
    if can_manual_regen:
        if st.button("🎲 Regenerar Menú Semanal (1 disp.)", use_container_width=True, help="Regenera el menú completo de esta semana aleatoriamente. Límite estricto: 1 sola vez por semana."):
            with st.spinner("Generando nueva combinación semanal..."):
                ok_regen, new_menu, new_meta, msg_regen = regenerate_menu_manually(dishes, meta, freezer_data=freezer_data)
                if ok_regen:
                    storage.save_current_menu(new_menu)
                    storage.save_generation_meta(new_meta)
                    updated_vetos = reset_weekly_vetos(vetos_state)
                    storage.save_vetos(updated_vetos)
                    st.success("¡Menú regenerado con éxito! Se ha consumido la única regeneración manual de esta semana.")
                    st.rerun()
                else:
                    st.error(msg_regen)
    else:
        st.button(
            "🔒 Regeneración Agotada (0/1 disp.)", 
            disabled=True, 
            use_container_width=True, 
            help="Ya se ha utilizado la única regeneración manual permitida para esta semana. El menú completo está fijado. Para cambiar platos individuales, utiliza tus 2 vetos individuales."
        )

    # Botón rápido para enviar email
    if st.button("✉️ Enviar Menú por Email", use_container_width=True, type="primary"):
        with st.spinner("Enviando correo con el menú semanal..."):
            ok, msg = send_weekly_menu_email(settings, current_menu, is_test=False)
            if ok:
                st.success("¡Email enviado con éxito a ambos!")
            else:
                st.error(f"Error al enviar: {msg}")

    # Botón para exportar el menú al calendario
    menu_ics_data = generate_menu_ics(current_menu, f"Menú Semanal AyA ({cycle_desc})")
    st.download_button(
        "📅 Exportar al Calendario (.ics)",
        data=menu_ics_data,
        file_name="menu_semanal_AyA.ics",
        mime="text/calendar",
        use_container_width=True,
        help="Descarga el archivo .ics para añadir las 14 comidas y cenas a Google Calendar o al iPhone con 1 clic."
    )

    # Ventana de cambios y vetos (Sábado -> Domingo 16:00)
    is_window_open, window_msg, window_dt = get_veto_window_status()

    st.markdown("#### ⏰ Plazo de Cambios y Vetos")
    if is_window_open:
        st.success(f"🟢 **Plazo ABIERTO**\n\n{window_msg}")
    else:
        st.warning("🔒 **Plazo CERRADO**\n\nFinalizó el domingo a las 16:00. Menú semanal confirmado.")

    override_window = st.checkbox(
        "🔓 Permitir cambios fuera de plazo",
        value=False,
        help="Actívalo si necesitas aplicar un veto o cambio excepcional una vez pasado el domingo a las 16:00 (o en modo pruebas)."
    )

    # Botón rápido para sincronizar con Google Sheets (Platos y Congelador en el mismo archivo)
    if st.button("🔄 Sincronizar Google Sheets", use_container_width=True):
        sheet_url = settings.get("sheet_url", "")
        gid_dishes = settings.get("sheet_gid_dishes", "83672031")
        gid_freezer = settings.get("sheet_gid_freezer", "797240193")
        with st.spinner("Descargando recetas y estado del congelador..."):
            loaded_dishes, msg = fetch_dishes_from_csv(sheet_url, gid=gid_dishes)
            loaded_freezer, f_msg = fetch_freezer_from_csv(sheet_url, gid=gid_freezer)
            if loaded_dishes:
                storage.save_dishes(loaded_dishes)
            if loaded_freezer:
                f_data = storage.get_freezer()
                f_data["items"] = loaded_freezer
                storage.save_freezer(f_data)
            st.success(f"¡Sincronizado! {msg} • {f_msg}")
            st.rerun()

    st.divider()
    st.caption("Aplicación multiplataforma accesible desde móvil (iOS / Android) y ordenador.")


# --- PESTAÑAS PRINCIPALES ---
tab_menu, tab_vetos, tab_congelador, tab_cupones, tab_lista, tab_recetas, tab_ajustes = st.tabs([
    "📅 Menú Semanal",
    "🚫 Sistema de Vetos",
    "🧊 Congelador",
    "🎟️ Cupones e Invitaciones",
    "🛒 Lista de la Compra",
    "🥗 Catálogo de Recetas",
    "⚙️ Ajustes & Correo"
])


# ==============================================================================
# TAB 1: MENÚ SEMANAL
# ==============================================================================
with tab_menu:
    st.subheader("🗓️ Planificación de la Semana")

    t_col1, t_col2 = st.columns([3, 1])
    with t_col1:
        if is_window_open:
            st.info(f"⏱️ **Plazo de cambios ABIERTO:** Álvaro y Ana podéis aplicar vuestros 2 vetos antes del **domingo a las 16:00** ({window_msg}).")
        elif override_window:
            st.warning("🔓 **Modo desbloqueado (Excepción / Pruebas):** Permitido aplicar vetos fuera del plazo habitual.")
        else:
            st.error("🔒 **Menú Confirmado (Plazo cerrado):** El plazo para realizar cambios finalizó el **domingo a las 16:00**. El menú semanal está cerrado. Para hacer excepciones, activa 'Permitir cambios fuera de plazo' en el menú lateral.")
    with t_col2:
        if can_manual_regen:
            if st.button("🎲 Regenerar Menú (1 disp.)", key="btn_regen_tab_menu", help="Regenera todo el menú semanal una única vez si no os convence. Límite: 1 vez por semana."):
                with st.spinner("Regenerando menú completo..."):
                    ok_regen, new_menu, new_meta, msg_regen = regenerate_menu_manually(dishes, meta, freezer_data=freezer_data)
                    if ok_regen:
                        storage.save_current_menu(new_menu)
                        storage.save_generation_meta(new_meta)
                        updated_vetos = reset_weekly_vetos(vetos_state)
                        storage.save_vetos(updated_vetos)
                        st.success("¡Menú semanal regenerado con éxito!")
                        st.rerun()
                    else:
                        st.error(msg_regen)
        else:
            st.caption("🔒 **Regeneración manual:** Agotada (1/1 usada esta semana). Menú fijado.")

    # Expander para sincronizar y añadir el menú a los calendarios
    with st.expander("📲 Añadir Menú Completo a Google Calendar / iPhone", expanded=False):
        st.markdown("""
        Puedes añadir automáticamente todas las comidas y cenas de esta semana al calendario de Álvaro y Ana:
        - 🍏 **En iPhone / iPad:** Pulsa el botón de descarga inferior. Tu iPhone te preguntará si quieres añadir los 14 eventos: selecciona el calendario **AyA** y pulsa *"Añadir todos"*.
        - 🤖 **En Google Calendar (PC o Android):** Descarga el archivo `.ics` y en [Google Calendar](https://calendar.google.com) ve a *Ajustes (⚙️) > Importar y exportar > Importar* y elige el calendario **AyA**.
        """)
        st.download_button(
            "📥 Descargar Menú para Calendario (.ics)",
            data=menu_ics_data,
            file_name="menu_semanal_AyA.ics",
            mime="text/calendar",
            type="primary",
            use_container_width=True,
            key="btn_download_ics_tab1"
        )

    st.caption("Sustituye cualquier comida o cena de forma individual con vuestros vetos respetando las normas de la casa.")

    freezer_items_active = set(
        k for k, v in freezer_data.get("items", {}).items() 
        if (isinstance(v, int) and v > 0) or (isinstance(v, dict) and v.get("portions", 1) > 0)
    )

    for day_data in current_menu:
        day_name = day_data.get("day", "")
        comida = day_data.get("comida", {})
        cena = day_data.get("cena", {})

        c_badge_f = '<span class="badge-freezer">🧊 Tupper listo</span>' if comida.get('name') in freezer_items_active else ''
        ce_badge_f = '<span class="badge-freezer">🧊 Tupper listo</span>' if cena.get('name') in freezer_items_active else ''

        day_info = cal_week_map.get(day_name, {})
        day_events = day_info.get("events", [])
        day_date_obj = day_info.get("date")
        date_suffix = f" • {day_info.get('date_str', '')}" if day_info.get("date_str") else ""

        # Comprobar si es festivo oficial (por ej. 12 de octubre)
        h_name = get_holiday_name(day_date_obj) if day_date_obj else day_data.get("holiday_name")
        is_holiday_day = (h_name is not None) or day_data.get("is_holiday", False)
        is_festive_day = is_holiday_day or (day_name in ["Sábado", "Domingo"])

        st.markdown(f"### 📍 {day_name}{date_suffix}")

        if is_holiday_day:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%); border: 1px solid #F59E0B; border-left: 5px solid #D97706; padding: 8px 14px; border-radius: 8px; margin-bottom: 12px; color: #92400E; font-size: 0.9rem; font-weight: 600;">
                🎉 <strong>¡DÍA FESTIVO!</strong> {h_name or 'Festivo oficial'} • <em>Comida elaborada / especial recomendada</em>
            </div>
            """, unsafe_allow_html=True)

        if day_events:
            for ev in day_events:
                ev_time = f" ({ev['start'].strftime('%H:%M')})" if not ev.get('is_all_day') and ev.get('start') else ""
                st.markdown(f"""
                <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-left: 4px solid #3B82F6; padding: 6px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.88rem; color: #1E40AF;">
                    🗓️ <strong>Evento AyA:</strong> {ev['summary']}{ev_time}
                </div>
                """, unsafe_allow_html=True)

        c_comida, c_cena = st.columns(2)

        # Tarjeta Comida
        with c_comida:
            festive_badge = '<span style="background-color: #FEF3C7; color: #B45309; font-weight: 600; font-size: 0.75rem; padding: 2px 8px; border-radius: 9999px; margin-left: 6px;">🍲 Elaborada</span>' if is_festive_day else ''
            c_cal_url = get_google_calendar_url(f"☀️ Comida: {comida.get('name')}", day_data.get('date', ''), 14, details=f"Ingredientes: {comida.get('ingredients', '')}")
            cal_link_c = f'<div style="text-align: right; margin-top: 4px;"><a href="{c_cal_url}" target="_blank" style="font-size: 0.8rem; text-decoration: none; color: #2563EB;">📅 Añadir a Google Cal</a></div>' if c_cal_url else ''
            st.markdown(f"""
            <div class="dish-card">
                <span class="badge-comida">☀️ ALMUERZO</span>{festive_badge}{c_badge_f}
                <div class="dish-title">{comida.get('name', 'No asignado')}</div>
                <div class="dish-ing"><em>Ingredientes:</em> {comida.get('ingredients', 'Sin ingredientes')}</div>
                {cal_link_c}
            </div>
            """, unsafe_allow_html=True)

            with st.expander(f"🚫 Vetar comida del {day_name}"):
                veto_user = st.radio(
                    f"¿Quién veta la comida?",
                    ["Álvaro", "Ana"],
                    key=f"veto_user_comida_{day_name}",
                    horizontal=True
                )
                if st.button(f"Confirmar Veto ({veto_user})", key=f"btn_veto_comida_{day_name}"):
                    if not is_window_open and not override_window:
                        st.error("🔒 El plazo para realizar cambios y vetos finalizó el domingo a las 16:00. Activa 'Permitir cambios fuera de plazo' en la barra lateral si necesitas hacer una excepción.")
                    else:
                        ok, updated_menu, updated_vetos, msg, new_dish = apply_veto(
                            veto_user, day_name, "comida", current_menu, dishes, vetos_state, freezer_data=freezer_data
                        )
                        if ok:
                            storage.save_current_menu(updated_menu)
                            storage.save_vetos(updated_vetos)
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # Tarjeta Cena
        with c_cena:
            ce_cal_url = get_google_calendar_url(f"🌙 Cena: {cena.get('name')}", day_data.get('date', ''), 21, details=f"Ingredientes: {cena.get('ingredients', '')}")
            cal_link_ce = f'<div style="text-align: right; margin-top: 4px;"><a href="{ce_cal_url}" target="_blank" style="font-size: 0.8rem; text-decoration: none; color: #2563EB;">📅 Añadir a Google Cal</a></div>' if ce_cal_url else ''
            st.markdown(f"""
            <div class="dish-card">
                <span class="badge-cena">🌙 CENA</span>{ce_badge_f}
                <div class="dish-title">{cena.get('name', 'No asignado')}</div>
                <div class="dish-ing"><em>Ingredientes:</em> {cena.get('ingredients', 'Sin ingredientes')}</div>
                {cal_link_ce}
            </div>
            """, unsafe_allow_html=True)

            with st.expander(f"🚫 Vetar cena del {day_name}"):
                veto_user_cena = st.radio(
                    f"¿Quién veta la cena?",
                    ["Álvaro", "Ana"],
                    key=f"veto_user_cena_{day_name}",
                    horizontal=True
                )
                if st.button(f"Confirmar Veto ({veto_user_cena})", key=f"btn_veto_cena_{day_name}"):
                    if not is_window_open and not override_window:
                        st.error("🔒 El plazo para realizar cambios y vetos finalizó el domingo a las 16:00. Activa 'Permitir cambios fuera de plazo' en la barra lateral si necesitas hacer una excepción.")
                    else:
                        ok, updated_menu, updated_vetos, msg, new_dish = apply_veto(
                            veto_user_cena, day_name, "cena", current_menu, dishes, vetos_state, freezer_data=freezer_data
                        )
                        if ok:
                            storage.save_current_menu(updated_menu)
                            storage.save_vetos(updated_vetos)
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        st.write("")


# ==============================================================================
# TAB 2: SISTEMA DE VETOS
# ==============================================================================
with tab_vetos:
    st.subheader("🚫 Estado de Vetos Semanales")
    st.write(f"Cada persona dispone de un límite estricto de **{VETO_LIMIT_PER_PERSON} vetos por semana**.")
    st.caption("⏰ **Ventana de decisión:** Los cambios y vetos solo pueden aplicarse entre la ejecución del menú (**sábado**) y el **domingo antes de las 16:00**.")

    v_col1, v_col2 = st.columns(2)
    with v_col1:
        st.markdown(f"#### 👨 Álvaro: **{alvaro_vetos_left} disponibles**")
        st.progress(alvaro_vetos_left / VETO_LIMIT_PER_PERSON)
        st.caption(f"Usados esta semana: {vetos_state.get('alvaro_used', 0)} / {VETO_LIMIT_PER_PERSON}")

    with v_col2:
        ana_used = vetos_state.get('ana_used', vetos_state.get('pareja_used', 0))
        st.markdown(f"#### 👩 Ana: **{ana_vetos_left} disponibles**")
        st.progress(ana_vetos_left / VETO_LIMIT_PER_PERSON)
        st.caption(f"Usados esta semana: {ana_used} / {VETO_LIMIT_PER_PERSON}")

    st.divider()

    # Historial de cambios
    st.subheader("📜 Historial de Vetos Aplicados")
    history = vetos_state.get("history", [])
    if history:
        df_history = pd.DataFrame(history)
        df_history = df_history[["timestamp", "user", "day", "meal_type", "old_dish", "new_dish"]]
        df_history.columns = ["Fecha / Hora", "Persona", "Día", "Momento", "Plato Retirado", "Nuevo Plato"]
        st.dataframe(df_history, use_container_width=True)
    else:
        st.info("Aún no se ha aplicado ningún veto esta semana.")

    st.write("")
    if st.button("🔄 Reiniciar Vetos Semanales (Poner a 2 disponibles para Álvaro y Ana)"):
        new_vetos = reset_weekly_vetos(vetos_state)
        storage.save_vetos(new_vetos)
        st.success("¡Vetos reiniciados a 2 para Álvaro y 2 para Ana!")
        st.rerun()


# ==============================================================================
# ==============================================================================
# TAB 3: CONGELADOR & ALIMENTOS (GOOGLE SHEETS)
# ==============================================================================
with tab_congelador:
    st.subheader("🧊 Control de Congelador (Hoja Google Sheets)")
    st.caption("Esta sección está vinculada a la pestaña **'congelador'** de vuestro Google Sheets. Los alimentos marcados con 'Sí' **habilitan** los platos correspondientes en el menú y vetos. Los marcados con 'No' quedan **deshabilitados** (sin dar prioridad a ninguno).")

    items_in_freezer = freezer_data.get("items", {})

    # Botón directo para sincronizar la hoja de congelador
    c_btn1, c_btn2 = st.columns([2, 1])
    with c_btn1:
        if st.button("🔄 Sincronizar 'congelador' desde Google Sheets", use_container_width=True, type="primary"):
            sheet_url = settings.get("sheet_url", "")
            gid_freezer = settings.get("sheet_gid_freezer", "797240193")
            with st.spinner("Descargando estado de la hoja congelador..."):
                loaded_freezer, f_msg = fetch_freezer_from_csv(sheet_url, gid=gid_freezer)
                if loaded_freezer:
                    freezer_data["items"] = loaded_freezer
                    storage.save_freezer(freezer_data)
                    st.success(f"¡Sincronizado! {f_msg}")
                    st.rerun()
                else:
                    st.warning(f_msg)
    with c_btn2:
        st.caption(f"Última lectura: **{len(items_in_freezer)} alimentos** registrados en la hoja.")

    st.divider()

    # Métricas
    enabled_count = len([k for k, v in items_in_freezer.items() if (isinstance(v, bool) and v) or (isinstance(v, str) and v.lower() in ['si', 'sí', 'true', '1'])])
    disabled_count = len(items_in_freezer) - enabled_count

    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric("🟢 Alimentos con existencias (Habilitados)", f"{enabled_count} alimentos")
    with m_col2:
        st.metric("🔴 Alimentos agotados (Deshabilitados)", f"{disabled_count} alimentos")

    st.divider()

    st.markdown("#### 📋 Estado actual de los alimentos en el congelador")
    st.caption("Puedes consultar el estado o cambiarlo con 1 clic aquí mismo (se guardará también localmente):")

    for item_name, status in items_in_freezer.items():
        is_available = status if isinstance(status, bool) else (str(status).lower() in ["si", "sí", "true", "1"])
        
        # Encontrar platos de la lista afectados
        from menu_generator import normalize_text
        norm_it = normalize_text(item_name)
        synonyms = [norm_it]
        if "pollo" in norm_it: synonyms.append("pollo")
        matched = []
        for d in dishes:
            d_name_norm = normalize_text(d["name"])
            d_ing_norm = normalize_text(d["ingredients"])
            if any(s in d_name_norm or s in d_ing_norm for s in synonyms):
                matched.append(d["name"])

        matched_str = ", ".join(matched) if matched else "Sin platos directos vinculados"

        with st.container():
            card_col1, card_col2 = st.columns([3, 1])
            with card_col1:
                status_badge = "🟢 **DISPONIBLE (Sí)**" if is_available else "🔴 **AGOTADO (No)**"
                st.markdown(f"**🍲 {item_name}** — {status_badge}")
                st.caption(f"*Habilita los platos:* {matched_str}")
            with card_col2:
                btn_label = "Marcar como NO" if is_available else "Marcar como SÍ"
                btn_type = "secondary" if is_available else "primary"
                if st.button(btn_label, key=f"tgl_sheet_{item_name}", type=btn_type, use_container_width=True):
                    items_in_freezer[item_name] = not is_available
                    freezer_data["items"] = items_in_freezer
                    storage.save_freezer(freezer_data)
                    st.rerun()

            st.write("")


# ==============================================================================
# TAB 4: CUPONES E INVITACIONES PARA COMER FUERA
# ==============================================================================
with tab_cupones:
    st.subheader("🎟️ Invitaciones y Cupones para Pedir o Comer Fuera")
    st.caption("Gestiona invitaciones, cenas pendientes y cupones de descuento con alertas de caducidad.")

    # Filtro
    f_col1, f_col2 = st.columns([1, 1])
    with f_col1:
        filtro_user = st.selectbox("Filtrar por destinatario:", ["Todos", "Álvaro", "Ana"])
    with f_col2:
        filtro_status = st.selectbox("Filtrar por estado:", ["Todos", "Pendientes", "Usados / Canjeados"])

    # Lista filtrada
    filtered_coupons = get_coupons_by_user(coupons, filtro_user)
    if filtro_status == "Pendientes":
        filtered_coupons = [c for c in filtered_coupons if c.get("status") == "pendiente"]
    elif filtro_status == "Usados / Canjeados":
        filtered_coupons = [c for c in filtered_coupons if c.get("status") == "usado"]

    if filtered_coupons:
        for c in filtered_coupons:
            c_id = c.get("id")
            user_owner = c.get("user", "")
            badge_class = "badge-alvaro" if user_owner == "Álvaro" else "badge-ana"
            exp_date = c.get("expiration_date", "")
            code, exp_msg, exp_color = check_expiration_warning(exp_date)
            status = c.get("status", "pendiente")

            with st.container():
                st.markdown(f"""
                <div style="background: {'#FAFAFA' if status == 'usado' else '#FFFFFF'}; border: 1px solid {'#CBD5E1' if status == 'usado' else '#E2E8F0'}; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="{badge_class}">👤 {user_owner}</span>
                        <span style="color: {exp_color}; font-weight: 700; font-size: 0.85rem;">⏳ {exp_msg}</span>
                    </div>
                    <h4 style="margin: 8px 0 4px 0; color: {'#94A3B8' if status == 'usado' else '#1E293B'}; text-decoration: {'line-through' if status == 'usado' else 'none'};">{c.get('title')}</h4>
                    <p style="margin: 0 0 6px 0; font-weight: 600; color: #475569;">📍 Restaurante: {c.get('restaurant', 'No especificado')}</p>
                    <p style="margin: 0; font-size: 0.85rem; color: #64748B;">📝 <em>{c.get('notes', 'Sin notas')}</em></p>
                </div>
                """, unsafe_allow_html=True)

                act_col1, act_col2 = st.columns([2, 1])
                with act_col1:
                    btn_label = "✅ Marcar como Canjeado" if status == "pendiente" else "↩️ Reactivar Cupón"
                    if st.button(btn_label, key=f"toggle_{c_id}"):
                        new_list, new_st = toggle_coupon_status(coupons, c_id)
                        storage.save_coupons(new_list)
                        st.rerun()
                with act_col2:
                    if st.button("🗑️ Eliminar", key=f"del_{c_id}"):
                        new_list = delete_coupon(coupons, c_id)
                        storage.save_coupons(new_list)
                        st.rerun()
    else:
        st.info("No hay cupones que coincidan con los filtros seleccionados.")

    st.divider()

    # Formulario para añadir cupón
    st.subheader("➕ Añadir Nueva Invitación o Cupón")
    with st.form("form_add_coupon", clear_on_submit=True):
        a_col1, a_col2 = st.columns(2)
        with a_col1:
            new_title = st.text_input("Título de la invitación / cupón *", placeholder="Ej: Cena de Sushi para 2")
            new_rest = st.text_input("Restaurante o tipo de comida", placeholder="Ej: Goiko Grill / Comida Mexicana")
            new_user = st.selectbox("¿A quién pertenece / Quién invita?", ["Álvaro", "Ana"])
        with a_col2:
            new_date = st.date_input("Fecha de caducidad", min_value=datetime.now().date(), value=datetime.now().date() + timedelta(days=30))
            new_notes = st.text_area("Condiciones o notas", placeholder="Ej: Válido solo de lunes a jueves en local.")

        if st.form_submit_button("Guardar Cupón", type="primary"):
            if new_title.strip():
                coupon_dict = create_coupon(
                    user=new_user,
                    title=new_title,
                    restaurant=new_rest,
                    expiration_date=str(new_date),
                    notes=new_notes
                )
                updated_coupons = add_coupon(coupons, coupon_dict)
                storage.save_coupons(updated_coupons)
                st.success("¡Cupón guardado correctamente!")
                st.rerun()
            else:
                st.error("Por favor, introduce al menos un título para el cupón.")


# ==============================================================================
# TAB 4: LISTA DE LA COMPRA CONSOLIDADA
# ==============================================================================
with tab_lista:
    st.subheader("🛒 Lista de la Compra Consolidada")
    st.caption("Ingredientes necesarios para cocinar todos los almuerzos y cenas de esta semana:")

    all_ingredients = []
    dish_ingredient_map = []

    for day in current_menu:
        for meal in ["comida", "cena"]:
            m_data = day.get(meal, {})
            name = m_data.get("name", "")
            raw_ing = m_data.get("ingredients", "")
            if raw_ing:
                dish_ingredient_map.append({"Día": day.get("day"), "Plato": f"{name} ({meal.capitalize()})", "Ingredientes": raw_ing})
                for item in raw_ing.split(","):
                    item_clean = item.strip().capitalize()
                    if item_clean and item_clean not in all_ingredients:
                        all_ingredients.append(item_clean)

    all_ingredients.sort()

    if all_ingredients:
        # Checkbox interactivo para ir tachando en el supermercado
        st.write(f"**Total ingredientes distintos:** {len(all_ingredients)}")
        cols = st.columns(2)
        for i, ing in enumerate(all_ingredients):
            with cols[i % 2]:
                st.checkbox(ing, key=f"shop_item_{i}")

        st.divider()
        st.markdown("#### 📋 Copiar lista en texto plano para WhatsApp:")
        formatted_list = "🛒 *LISTA DE LA COMPRA SEMANAL:*\n" + "\n".join([f"• {ing}" for ing in all_ingredients])
        st.code(formatted_list, language="text")

        with st.expander("🔍 Ver desglose plato por plato"):
            st.dataframe(pd.DataFrame(dish_ingredient_map), use_container_width=True)
    else:
        st.info("No hay ingredientes registrados en el menú actual.")


# ==============================================================================
# TAB 5: CATÁLOGO DE RECETAS
# ==============================================================================
with tab_recetas:
    st.subheader("🥗 Base de Datos de Recetas")
    st.write(f"Actualmente hay **{len(dishes)} platos disponibles** en la base de datos local.")

    # Filtros y buscador
    rf_col1, rf_col2 = st.columns([1, 2])
    with rf_col1:
        tipo_filtro = st.selectbox("Filtrar por momento:", ["Todos", "Comida", "Cena", "Ambas"])
    with rf_col2:
        search_query = st.text_input("🔍 Buscar por nombre o ingrediente:", "")

    # Filtrar
    filtered_dishes = list(dishes)
    if tipo_filtro != "Todos":
        filtered_dishes = [d for d in filtered_dishes if d.get("type", "").lower() == tipo_filtro.lower()]
    if search_query.strip():
        q = search_query.lower()
        filtered_dishes = [
            d for d in filtered_dishes 
            if q in d.get("name", "").lower() or q in d.get("ingredients", "").lower()
        ]

    if filtered_dishes:
        df_dishes = pd.DataFrame(filtered_dishes)
        if "id" in df_dishes.columns:
            df_dishes = df_dishes[["name", "type", "ingredients"]]
        df_dishes.columns = ["Nombre del Plato", "Tipo", "Ingredientes"]
        st.dataframe(df_dishes, use_container_width=True)
    else:
        st.warning("No se encontraron recetas con ese criterio.")

    st.divider()

    # Añadir receta manualmente
    with st.expander("➕ Añadir Plato Manualmente"):
        with st.form("form_add_dish", clear_on_submit=True):
            nd_name = st.text_input("Nombre del plato *")
            nd_type = st.selectbox("Tipo de plato", ["comida", "cena", "ambas"])
            nd_ing = st.text_input("Ingredientes (separados por comas)", placeholder="Ej: Arroz, tomate, pollo, cebolla")
            if st.form_submit_button("Guardar Receta en Base de Datos"):
                if nd_name.strip():
                    new_dish = {
                        "id": str(len(dishes) + 1),
                        "name": nd_name.strip(),
                        "type": nd_type,
                        "ingredients": nd_ing.strip()
                    }
                    dishes.append(new_dish)
                    storage.save_dishes(dishes)
                    st.success(f"¡Receta '{nd_name}' añadida con éxito!")
                    st.rerun()
                else:
                    st.error("Debes escribir un nombre para el plato.")


# ==============================================================================
# TAB 6: AJUSTES & CORREO
# ==============================================================================
with tab_ajustes:
    st.subheader("⚙️ Configuración del Sistema")

    with st.form("settings_form"):
        st.markdown("#### 1. Google Sheets (Mismo archivo para Platos y Congelador)")
        st.caption("Ambas hojas pertenecen al mismo documento de Google Sheets en pestañas distintas.")
        sheet_url_input = st.text_input(
            "Enlace del archivo de Google Sheets:",
            value=settings.get("sheet_url", ""),
            help="Enlace completo del documento compartido."
        )
        gid_col1, gid_col2 = st.columns(2)
        with gid_col1:
            sheet_gid_dishes = st.text_input(
                "GID Pestaña Platos:",
                value=str(settings.get("sheet_gid_dishes", "83672031")),
                help="El identificador de pestaña (gid=...) de la hoja de platos."
            )
        with gid_col2:
            sheet_gid_freezer = st.text_input(
                "GID Pestaña Congelador:",
                value=str(settings.get("sheet_gid_freezer", "797240193")),
                help="El identificador de pestaña (gid=...) de la hoja de congelador."
            )

        st.markdown("#### 2. Servidor de Correo (SMTP)")
        smtp_col1, smtp_col2 = st.columns(2)
        with smtp_col1:
            smtp_host = st.text_input("Servidor SMTP:", value=settings.get("smtp_host", "smtp.gmail.com"))
            smtp_port = st.number_input("Puerto SMTP:", value=int(settings.get("smtp_port", 587)), step=1)
            smtp_user = st.text_input("Usuario / Email emisor:", value=settings.get("smtp_user", ""))
        with smtp_col2:
            smtp_pass = st.text_input(
                "Contraseña de Aplicación (Gmail):", 
                value=settings.get("smtp_password", ""), 
                type="password",
                help="Genera una contraseña de 16 letras en: https://myaccount.google.com/apppasswords (no uses tu contraseña habitual de Gmail)"
            )
            recipients = st.text_input(
                "Destinatarios (separados por comas):", 
                value=settings.get("recipients", "alv.mmartin@gmail.com, absaladomoreno@gmail.com")
            )
            smtp_tls = st.checkbox("Usar STARTTLS (Recomendado puerto 587)", value=settings.get("smtp_use_tls", True))
            st.caption("ℹ️ *Gmail requiere una contraseña de 16 caracteres creada en [Google Contraseñas de Aplicación](https://myaccount.google.com/apppasswords).*")

        st.markdown("#### 3. Calendario Compartido AyA (Google Calendar)")
        st.caption("Dirección secreta iCal (.ics) para sincronizar en tiempo real los eventos y planes de Álvaro y Ana:")
        calendar_ics_input = st.text_input(
            "Enlace secreto iCal (.ics) del calendario:",
            value=settings.get("calendar_ics_url", ""),
            help="Enlace privado .ics obtenido desde Google Calendar para sincronizar eventos y planes."
        )

        if st.form_submit_button("💾 Guardar Configuración", type="primary"):
            new_settings = {
                "sheet_url": sheet_url_input.strip(),
                "sheet_gid_dishes": sheet_gid_dishes.strip(),
                "sheet_gid_freezer": sheet_gid_freezer.strip(),
                "calendar_ics_url": calendar_ics_input.strip(),
                "smtp_host": smtp_host.strip(),
                "smtp_port": int(smtp_port),
                "smtp_user": smtp_user.strip(),
                "smtp_password": smtp_pass.strip(),
                "smtp_use_tls": smtp_tls,
                "recipients": recipients.strip()
            }
            storage.update_settings(new_settings)
            st.success("¡Configuración guardada correctamente en el sistema!")
            st.rerun()

    st.write("")
    st.markdown("#### 🧪 Prueba de Conexión de Correo")
    if st.button("Enviar Correo de Prueba"):
        with st.spinner("Conectando con el servidor SMTP y enviando correo de prueba..."):
            ok, msg = send_weekly_menu_email(settings, current_menu, is_test=True)
            if ok:
                st.success(f"¡Prueba exitosa! {msg}")
            else:
                st.error(f"Fallo en la prueba: {msg}")

import streamlit as st
from datetime import datetime, date, timedelta
import pandas as pd
import logging

from storage_manager import StorageManager
from menu_generator import generate_weekly_menu, DAYS_OF_WEEK
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

# Configuración de página responsive y moderna
st.set_page_config(
    page_title="Menú Semanal - Álvaro & Ana",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar StorageManager (siempre sincronizado con el archivo JSON)
storage = StorageManager()

# Cargar datos iniciales si no existen
dishes = storage.get_dishes()
if not dishes:
    dishes = get_sample_dishes()
    storage.save_dishes(dishes)

current_menu = storage.get_current_menu()
if not current_menu:
    current_menu = generate_weekly_menu(dishes)
    storage.save_current_menu(current_menu)

vetos_state = storage.get_vetos()
settings = storage.get_settings()
coupons = storage.get_coupons()
meta = storage.get_generation_meta()
freezer_data = storage.get_freezer()

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

current_week_num = datetime.now().isocalendar()[1]
current_date_str = datetime.now().strftime("%d/%m/%Y")

st.markdown(f"""
<div class="main-header">
    <h1 style="margin: 0; font-size: 1.8rem;">🍽️ Planificador de Menú Semanal</h1>
    <p style="margin: 4px 0 0 0; opacity: 0.9; font-size: 0.95rem;">Aplicación privada para Álvaro & Ana • <strong>Semana {current_week_num}</strong> del año ({current_date_str})</p>
</div>
""", unsafe_allow_html=True)

# Métricas superiores en columnas
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("👨 Vetos Álvaro", f"{alvaro_vetos_left} / {VETO_LIMIT_PER_PERSON} disp.")
with col2:
    st.metric("👩 Vetos Ana", f"{ana_vetos_left} / {VETO_LIMIT_PER_PERSON} disp.")
with col3:
    total_frozen = len([k for k, v in freezer_data.get("items", {}).items() if v is True or str(v).lower() in ['si', 'sí', 'true', '1']])
    st.metric("🧊 Congelador", f"{total_frozen} disp.")
with col4:
    pending_coupons = len([c for c in coupons if c.get("status") == "pendiente"])
    st.metric("🎟️ Cupones pendientes", pending_coupons, delta=f"{len(expiring_coupons)} por caducar" if expiring_coupons else None, delta_color="inverse")

# Alerta de cupones por caducar si los hay
if expiring_coupons:
    with st.container():
        st.warning(f"⚠️ **Atención:** Tienes **{len(expiring_coupons)} cupón(es)** a punto de caducar o caducados. Revisa la pestaña de Cupones.")

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.header("⚡ Acciones Rápidas")
    
    # Botón rápido para enviar email
    if st.button("✉️ Enviar Menú por Email", use_container_width=True, type="primary"):
        with st.spinner("Enviando correo con el menú semanal..."):
            ok, msg = send_weekly_menu_email(settings, current_menu, is_test=False)
            if ok:
                st.success("¡Email enviado con éxito a ambos!")
            else:
                st.error(f"Error al enviar: {msg}")

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

    if is_window_open:
        st.info(f"⏱️ **Plazo de cambios ABIERTO:** Álvaro y Ana podéis aplicar vuestros 2 vetos antes del **domingo a las 16:00** ({window_msg}).")
    elif override_window:
        st.warning("🔓 **Modo desbloqueado (Excepción / Pruebas):** Permitido aplicar vetos fuera del plazo habitual.")
    else:
        st.error("🔒 **Menú Confirmado (Plazo cerrado):** El plazo para realizar cambios finalizó el **domingo a las 16:00**. El menú semanal está cerrado. Para hacer excepciones, activa 'Permitir cambios fuera de plazo' en el menú lateral.")

    st.caption("Sustituye cualquier comida o cena de forma individual respetando las normas de la casa.")

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

        st.markdown(f"### 📍 {day_name}")
        c_comida, c_cena = st.columns(2)

        # Tarjeta Comida
        with c_comida:
            st.markdown(f"""
            <div class="dish-card">
                <span class="badge-comida">☀️ ALMUERZO</span>{c_badge_f}
                <div class="dish-title">{comida.get('name', 'No asignado')}</div>
                <div class="dish-ing"><em>Ingredientes:</em> {comida.get('ingredients', 'Sin ingredientes')}</div>
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
            st.markdown(f"""
            <div class="dish-card">
                <span class="badge-cena">🌙 CENA</span>{ce_badge_f}
                <div class="dish-title">{cena.get('name', 'No asignado')}</div>
                <div class="dish-ing"><em>Ingredientes:</em> {cena.get('ingredients', 'Sin ingredientes')}</div>
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

        if st.form_submit_button("💾 Guardar Configuración", type="primary"):
            new_settings = {
                "sheet_url": sheet_url_input.strip(),
                "sheet_gid_dishes": sheet_gid_dishes.strip(),
                "sheet_gid_freezer": sheet_gid_freezer.strip(),
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

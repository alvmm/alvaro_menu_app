import os
import time
import logging
from pathlib import Path
from typing import Optional
import toml
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from storage_manager import StorageManager
from menu_generator import (
    generate_weekly_menu, regenerate_menu_manually,
    get_current_menu_cycle_key, normalize_text,
    is_freezer_status_available, dish_matches_freezer_item,
    is_dish_in_freezer
)
from veto_manager import (
    apply_veto, reset_weekly_vetos, get_remaining_vetos,
    get_veto_window_status, VETO_LIMIT_PER_PERSON
)
from coupon_manager import (
    create_coupon, add_coupon, toggle_coupon_status, delete_coupon,
    get_expiring_coupons_alert, check_expiration_warning, normalize_coupon_user
)
from emailer import send_weekly_menu_email
from csv_loader import (
    fetch_dishes_from_csv, fetch_freezer_from_csv,
    get_sample_dishes, enrich_dishes_ingredients
)
from calendar_loader import fetch_calendar_events, get_events_for_menu_week
from holidays_manager import get_holiday_name, now_madrid
from calendar_exporter import generate_menu_ics, get_google_calendar_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

app = FastAPI(
    title="Menú Semanal AyA API",
    description="API profesional y PWA para la planificación del menú semanal de Álvaro y Ana",
    version="2.0.0"
)

# Caché en memoria para eventos de calendario iCal (TTL = 15 minutos)
_CALENDAR_CACHE = {
    "url": "",
    "timestamp": 0.0,
    "events": []
}
CALENDAR_CACHE_TTL = 900  # 15 min


def load_external_secrets() -> dict:
    """
    Carga secretos desde variables de entorno y/o .streamlit/secrets.toml (si existe),
    permitiendo compatibilidad directa en local y en servidores cloud (Render, Railway, Fly.io).
    """
    secrets = {"smtp": {}, "integrations": {}}

    if SECRETS_PATH.exists():
        try:
            parsed = toml.load(SECRETS_PATH)
            if isinstance(parsed.get("smtp"), dict):
                secrets["smtp"].update(parsed["smtp"])
            if isinstance(parsed.get("integrations"), dict):
                secrets["integrations"].update(parsed["integrations"])
        except Exception as e:
            logger.warning(f"No se pudo leer secrets.toml: {e}")

    # Variables de entorno tienen prioridad en producción
    env_map_smtp = {
        "SMTP_HOST": "host",
        "SMTP_PORT": "port",
        "SMTP_USER": "user",
        "SMTP_PASSWORD": "password",
        "SMTP_RECIPIENTS": "recipients",
    }
    for env_key, sec_key in env_map_smtp.items():
        val = os.environ.get(env_key)
        if val:
            secrets["smtp"][sec_key] = val

    env_map_integ = {
        "SHEET_URL": "sheet_url",
        "SHEET_GID_DISHES": "sheet_gid_dishes",
        "SHEET_GID_FREEZER": "sheet_gid_freezer",
        "CALENDAR_ICS_URL": "calendar_ics_url",
    }
    for env_key, sec_key in env_map_integ.items():
        val = os.environ.get(env_key)
        if val:
            secrets["integrations"][sec_key] = val

    return secrets


def get_cached_calendar_events(ics_url: str, force_refresh: bool = False) -> list[dict]:
    if not ics_url or not ics_url.strip():
        return []
    now_ts = time.time()
    if (
        not force_refresh
        and _CALENDAR_CACHE["url"] == ics_url
        and (now_ts - _CALENDAR_CACHE["timestamp"]) < CALENDAR_CACHE_TTL
    ):
        return _CALENDAR_CACHE["events"]

    events = fetch_calendar_events(ics_url)
    _CALENDAR_CACHE["url"] = ics_url
    _CALENDAR_CACHE["timestamp"] = now_ts
    _CALENDAR_CACHE["events"] = events
    return events


def clear_calendar_cache():
    _CALENDAR_CACHE["url"] = ""
    _CALENDAR_CACHE["timestamp"] = 0.0
    _CALENDAR_CACHE["events"] = []


def check_and_run_weekly_auto_generation(storage_instance: StorageManager, effective_settings: dict) -> tuple[bool, str]:
    now = now_madrid()
    cycle_key, cycle_desc = get_current_menu_cycle_key(now)

    meta_data = storage_instance.get_generation_meta()
    last_cycle = meta_data.get("last_auto_gen_week", "")
    current_menu_data = storage_instance.get_current_menu()

    needs_generation = (last_cycle != cycle_key) or (not current_menu_data)
    if not needs_generation:
        return False, cycle_desc

    logger.info(f"Nuevo ciclo detectado ({cycle_key}). Generando menú semanal automáticamente...")
    sheet_url = effective_settings.get("sheet_url", "")
    gid_dishes = effective_settings.get("sheet_gid_dishes", "83672031")
    gid_freezer = effective_settings.get("sheet_gid_freezer", "797240193")

    dishes_list = storage_instance.get_dishes()
    freezer_info = storage_instance.get_freezer()
    if sheet_url:
        try:
            loaded_dishes, _ = fetch_dishes_from_csv(sheet_url, gid=gid_dishes, existing_dishes=dishes_list)
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

    new_menu = generate_weekly_menu(dishes_list, freezer_data=freezer_info)
    storage_instance.save_current_menu(new_menu)

    current_vetos = storage_instance.get_vetos()
    updated_vetos = reset_weekly_vetos(current_vetos)
    storage_instance.save_vetos(updated_vetos)
    storage_instance.save_shopping_checked([])

    meta_data["last_auto_gen_week"] = cycle_key
    meta_data["manual_regens_this_week"] = 0
    meta_data["last_auto_gen_date"] = now.strftime("%Y-%m-%d %H:%M")
    storage_instance.save_generation_meta(meta_data)

    if effective_settings.get("auto_email_enabled", True) and effective_settings.get("smtp_password"):
        try:
            send_weekly_menu_email(effective_settings, new_menu, is_test=False)
        except Exception as e:
            logger.error(f"Error enviando email semanal automático: {e}")

    return True, cycle_desc


def build_application_state(storage_instance: Optional[StorageManager] = None, external_secrets: Optional[dict] = None) -> dict:
    st_mgr = storage_instance or StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    ext_secrets = load_external_secrets() if external_secrets is None else external_secrets
    saved_settings = st_mgr.get_settings()
    effective_settings = st_mgr.get_effective_settings(ext_secrets)


    auto_generated_now, cycle_desc = check_and_run_weekly_auto_generation(st_mgr, effective_settings)

    dishes = st_mgr.get_dishes()
    if not dishes:
        dishes = get_sample_dishes()
        st_mgr.save_dishes(dishes)
    else:
        dishes = enrich_dishes_ingredients(dishes)

    freezer_data = st_mgr.get_freezer()
    current_menu = st_mgr.get_current_menu()
    if not current_menu:
        current_menu = generate_weekly_menu(dishes, freezer_data=freezer_data)
        st_mgr.save_current_menu(current_menu)

    vetos_state = st_mgr.get_vetos()
    coupons = st_mgr.get_coupons()
    meta = st_mgr.get_generation_meta()

    # Calendario iCal
    calendar_ics_url = effective_settings.get("calendar_ics_url", "")
    cal_week_map = {}
    if calendar_ics_url:
        try:
            raw_events = get_cached_calendar_events(calendar_ics_url)
            cal_week_map = get_events_for_menu_week(raw_events)
        except Exception as e:
            logger.warning(f"Error cargando eventos del calendario AyA: {e}")

    # Enriquecer días del menú para el frontend
    enriched_menu = []
    for day_data in current_menu:
        day_name = day_data.get("day", "")
        comida = dict(day_data.get("comida", {}))
        cena = dict(day_data.get("cena", {}))

        # Asegurar ingredientes si algún plato del menú no los tenía
        if not comida.get("ingredients") and comida.get("name"):
            for d_cat in dishes:
                if normalize_text(d_cat.get("name", "")) == normalize_text(comida["name"]):
                    comida["ingredients"] = d_cat.get("ingredients", "")
                    break
        if not cena.get("ingredients") and cena.get("name"):
            for d_cat in dishes:
                if normalize_text(d_cat.get("name", "")) == normalize_text(cena["name"]):
                    cena["ingredients"] = d_cat.get("ingredients", "")
                    break

        comida["in_freezer"] = is_dish_in_freezer(comida, freezer_data)
        cena["in_freezer"] = is_dish_in_freezer(cena, freezer_data)

        day_info = cal_week_map.get(day_name, {})
        day_date_obj = day_info.get("date")
        date_str = day_info.get("date_str") or day_data.get("date_str", "")
        iso_date = day_data.get("date", "")
        if not iso_date and day_date_obj:
            iso_date = day_date_obj.strftime("%Y-%m-%d")

        comida["gcal_url"] = get_google_calendar_url(
            f"☀️ Comida: {comida.get('name', '')}",
            iso_date,
            14,
            details=f"Ingredientes: {comida.get('ingredients', '')}"
        )
        cena["gcal_url"] = get_google_calendar_url(
            f"🌙 Cena: {cena.get('name', '')}",
            iso_date,
            21,
            details=f"Ingredientes: {cena.get('ingredients', '')}"
        )

        h_name = get_holiday_name(day_date_obj) if day_date_obj else day_data.get("holiday_name")
        is_holiday_day = (h_name is not None) or day_data.get("is_holiday", False)
        is_festive_day = is_holiday_day or (day_name in ["Sábado", "Domingo"])

        formatted_events = []
        for ev in day_info.get("events", []):
            ev_time = ev["start"].strftime("%H:%M") if (not ev.get("is_all_day") and ev.get("start")) else ""
            formatted_events.append({
                "summary": ev.get("summary", ""),
                "time": ev_time,
                "is_all_day": bool(ev.get("is_all_day")),
                "location": ev.get("location", "")
            })

        enriched_menu.append({
            "day": day_name,
            "date": iso_date,
            "date_str": date_str,
            "is_holiday": is_holiday_day,
            "holiday_name": h_name,
            "is_festive": is_festive_day,
            "events": formatted_events,
            "comida": comida,
            "cena": cena
        })

    # Ventana y estado de vetos
    is_window_open, window_msg, _ = get_veto_window_status()
    alvaro_left = get_remaining_vetos("alvaro", vetos_state)
    ana_left = get_remaining_vetos("ana", vetos_state)
    manual_used = meta.get("manual_regens_this_week", 0)
    manual_left = max(0, 1 - manual_used)

    # Congelador enriquecido
    freezer_items_raw = freezer_data.get("items", {})
    freezer_items_list = []
    enabled_frozen_count = 0
    for item_name, status in freezer_items_raw.items():
        avail = is_freezer_status_available(status)
        if avail:
            enabled_frozen_count += 1
        matched_dishes = [d["name"] for d in dishes if dish_matches_freezer_item(d, item_name)]
        freezer_items_list.append({
            "name": item_name,
            "available": avail,
            "matched_dishes": matched_dishes
        })

    # Cupones enriquecidos
    expiring_alerts = get_expiring_coupons_alert(coupons)
    enriched_coupons = []
    for c in coupons:
        code, exp_msg, exp_color = check_expiration_warning(c.get("expiration_date", ""))
        enriched_coupons.append({
            **c,
            "user": normalize_coupon_user(c.get("user", "")),
            "exp_code": code,
            "exp_msg": exp_msg,
            "exp_color": exp_color
        })

    # Lista de la compra consolidada
    all_ingredients = []
    seen_norms = set()
    dish_breakdown = []
    for day_entry in enriched_menu:
        for meal_key in ["comida", "cena"]:
            m_data = day_entry.get(meal_key, {})
            name = m_data.get("name", "")
            raw_ing = m_data.get("ingredients", "")
            if raw_ing:
                dish_breakdown.append({
                    "day": day_entry["day"],
                    "dish": f"{name} ({meal_key.capitalize()})",
                    "ingredients": raw_ing
                })
                for item in raw_ing.split(","):
                    item_clean = item.strip().capitalize()
                    item_norm = normalize_text(item_clean)
                    if item_clean and item_norm not in seen_norms:
                        seen_norms.add(item_norm)
                        all_ingredients.append(item_clean)
    all_ingredients.sort()
    checked_saved = [ing for ing in st_mgr.get_shopping_checked() if ing in all_ingredients]

    return {
        "cycle_desc": cycle_desc,
        "auto_generated_now": auto_generated_now,
        "metrics": {
            "alvaro_vetos_left": alvaro_left,
            "ana_vetos_left": ana_left,
            "veto_limit": VETO_LIMIT_PER_PERSON,
            "manual_regens_left": manual_left,
            "frozen_available": enabled_frozen_count,
            "frozen_total": len(freezer_items_list),
            "pending_coupons": len([c for c in enriched_coupons if c.get("status") == "pendiente"]),
            "expiring_coupons": len(expiring_alerts)
        },
        "veto_window": {
            "is_open": is_window_open,
            "message": window_msg,
            "alvaro_used": vetos_state.get("alvaro_used", 0),
            "ana_used": vetos_state.get("ana_used", vetos_state.get("pareja_used", 0)),
            "history": list(reversed(vetos_state.get("history", [])))
        },
        "menu": enriched_menu,
        "freezer": {
            "items": freezer_items_list,
            "enabled_count": enabled_frozen_count,
            "disabled_count": len(freezer_items_list) - enabled_frozen_count
        },
        "coupons": enriched_coupons,
        "shopping": {
            "ingredients": all_ingredients,
            "checked": checked_saved,
            "breakdown": dish_breakdown
        },
        "dishes": dishes,
        "settings": {
            "saved": {
                "sheet_url": saved_settings.get("sheet_url", ""),
                "sheet_gid_dishes": str(saved_settings.get("sheet_gid_dishes", "83672031")),
                "sheet_gid_freezer": str(saved_settings.get("sheet_gid_freezer", "797240193")),
                "calendar_ics_url": saved_settings.get("calendar_ics_url", ""),
                "smtp_host": saved_settings.get("smtp_host", "smtp.gmail.com"),
                "smtp_port": int(saved_settings.get("smtp_port", 587)),
                "smtp_user": saved_settings.get("smtp_user", ""),
                "smtp_use_tls": bool(saved_settings.get("smtp_use_tls", True)),
                "recipients": saved_settings.get("recipients", ""),
                "has_saved_password": bool(saved_settings.get("smtp_password"))
            },
            "secrets_active": {
                "sheet_url": bool(effective_settings.get("sheet_url") and not saved_settings.get("sheet_url")),
                "calendar_ics_url": bool(effective_settings.get("calendar_ics_url") and not saved_settings.get("calendar_ics_url")),
                "smtp_user": bool(effective_settings.get("smtp_user") and not saved_settings.get("smtp_user")),
                "smtp_password": bool(effective_settings.get("smtp_password") and not saved_settings.get("smtp_password")),
                "recipients": bool(effective_settings.get("recipients") and not saved_settings.get("recipients"))
            }
        }
    }


# --- Modelos Pydantic ---

class VetoRequest(BaseModel):
    user: str
    day: str
    meal_type: str
    override_window: bool = False


class FreezerToggleRequest(BaseModel):
    item_name: str


class CouponCreateRequest(BaseModel):
    user: str
    title: str
    restaurant: str = ""
    expiration_date: str
    notes: str = ""


class ShoppingCheckedRequest(BaseModel):
    checked: list[str]


class DishUpsertRequest(BaseModel):
    name: str
    type: str = "ambas"
    ingredients: str = ""


class SettingsUpdateRequest(BaseModel):
    sheet_url: str = ""
    sheet_gid_dishes: str = "83672031"
    sheet_gid_freezer: str = "797240193"
    calendar_ics_url: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    recipients: str = ""


class EmailSendRequest(BaseModel):
    is_test: bool = False


# --- Endpoints REST API ---

@app.get("/api/state")
def api_get_state():
    return build_application_state()


@app.post("/api/menu/regenerate")
def api_regenerate_menu():
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    dishes = enrich_dishes_ingredients(st_mgr.get_dishes() or get_sample_dishes())
    meta = st_mgr.get_generation_meta()
    freezer_data = st_mgr.get_freezer()

    ok, new_menu, new_meta, msg = regenerate_menu_manually(dishes, meta, freezer_data=freezer_data)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    st_mgr.save_current_menu(new_menu)
    st_mgr.save_generation_meta(new_meta)
    st_mgr.save_vetos(reset_weekly_vetos(st_mgr.get_vetos()))
    st_mgr.save_shopping_checked([])
    return {"ok": True, "message": msg, "state": build_application_state(st_mgr)}


@app.post("/api/menu/veto")
def api_apply_veto(req: VetoRequest):
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    is_open, window_msg, _ = get_veto_window_status()
    if not is_open and not req.override_window:
        raise HTTPException(
            status_code=400,
            detail="El plazo para realizar cambios finalizó el domingo a las 16:00. Activa 'Permitir cambios fuera de plazo' si necesitas hacer una excepción."
        )

    dishes = enrich_dishes_ingredients(st_mgr.get_dishes() or get_sample_dishes())
    current_menu = st_mgr.get_current_menu()
    vetos_state = st_mgr.get_vetos()
    freezer_data = st_mgr.get_freezer()

    ok, updated_menu, updated_vetos, msg, new_dish = apply_veto(
        req.user, req.day, req.meal_type, current_menu, dishes, vetos_state, freezer_data=freezer_data
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    st_mgr.save_current_menu(updated_menu)
    st_mgr.save_vetos(updated_vetos)
    return {"ok": True, "message": msg, "new_dish": new_dish, "state": build_application_state(st_mgr)}


@app.post("/api/vetos/reset")
def api_reset_vetos():
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    updated = reset_weekly_vetos(st_mgr.get_vetos())
    st_mgr.save_vetos(updated)
    return {"ok": True, "message": "¡Vetos semanales reiniciados a 2 para Álvaro y 2 para Ana!", "state": build_application_state(st_mgr)}


@app.post("/api/sync")
def api_sync_sheets():
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    effective = st_mgr.get_effective_settings(load_external_secrets())
    sheet_url = effective.get("sheet_url", "")
    gid_dishes = effective.get("sheet_gid_dishes", "83672031")
    gid_freezer = effective.get("sheet_gid_freezer", "797240193")

    existing_dishes = st_mgr.get_dishes()
    loaded_dishes, msg_d = fetch_dishes_from_csv(sheet_url, gid=gid_dishes, existing_dishes=existing_dishes)
    loaded_freezer, msg_f = fetch_freezer_from_csv(sheet_url, gid=gid_freezer)

    if loaded_dishes:
        st_mgr.save_dishes(loaded_dishes)
    if loaded_freezer:
        f_data = st_mgr.get_freezer()
        f_data["items"] = loaded_freezer
        st_mgr.save_freezer(f_data)

    clear_calendar_cache()
    return {
        "ok": True,
        "message": f"¡Sincronizado! {msg_d} • {msg_f}",
        "state": build_application_state(st_mgr)
    }


@app.post("/api/freezer/toggle")
def api_toggle_freezer(req: FreezerToggleRequest):
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    freezer_data = st_mgr.get_freezer()
    items = freezer_data.get("items", {})
    if req.item_name not in items:
        raise HTTPException(status_code=404, detail=f"Alimento '{req.item_name}' no encontrado en el congelador.")

    curr_avail = is_freezer_status_available(items[req.item_name])
    items[req.item_name] = not curr_avail
    freezer_data["items"] = items
    st_mgr.save_freezer(freezer_data)

    new_label = "DISPONIBLE (Sí)" if not curr_avail else "AGOTADO (No)"
    return {
        "ok": True,
        "message": f"'{req.item_name}' marcado como {new_label}.",
        "state": build_application_state(st_mgr)
    }


@app.post("/api/coupons")
def api_create_coupon(req: CouponCreateRequest):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="El título del cupón es obligatorio.")
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    coupons = st_mgr.get_coupons()
    new_c = create_coupon(
        user=req.user,
        title=req.title,
        restaurant=req.restaurant,
        expiration_date=req.expiration_date,
        notes=req.notes
    )
    updated = add_coupon(coupons, new_c)
    st_mgr.save_coupons(updated)
    return {"ok": True, "message": "¡Cupón guardado correctamente!", "state": build_application_state(st_mgr)}


@app.patch("/api/coupons/{coupon_id}/toggle")
def api_toggle_coupon(coupon_id: str):
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    coupons = st_mgr.get_coupons()
    updated, new_st = toggle_coupon_status(coupons, coupon_id)
    st_mgr.save_coupons(updated)
    return {"ok": True, "message": f"Estado del cupón actualizado a '{new_st}'.", "state": build_application_state(st_mgr)}


@app.delete("/api/coupons/{coupon_id}")
def api_delete_coupon(coupon_id: str):
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    coupons = st_mgr.get_coupons()
    updated = delete_coupon(coupons, coupon_id)
    st_mgr.save_coupons(updated)
    return {"ok": True, "message": "Cupón eliminado.", "state": build_application_state(st_mgr)}


@app.put("/api/shopping/checked")
def api_update_shopping_checked(req: ShoppingCheckedRequest):
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    st_mgr.save_shopping_checked(req.checked)
    return {"ok": True, "state": build_application_state(st_mgr)}


@app.post("/api/dishes")
def api_add_dish(req: DishUpsertRequest):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="El nombre del plato es obligatorio.")
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    dishes = st_mgr.get_dishes()
    next_id = max([int(d.get("id", 0)) for d in dishes if str(d.get("id", "")).isdigit()] + [len(dishes)]) + 1
    new_dish = {
        "id": str(next_id),
        "name": req.name.strip(),
        "type": req.type.strip().lower(),
        "ingredients": req.ingredients.strip()
    }
    dishes.append(new_dish)
    st_mgr.save_dishes(dishes)
    return {"ok": True, "message": f"¡Receta '{new_dish['name']}' añadida!", "state": build_application_state(st_mgr)}


@app.put("/api/dishes/{dish_id}")
def api_update_dish(dish_id: str, req: DishUpsertRequest):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="El nombre del plato no puede estar vacío.")
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    dishes = st_mgr.get_dishes()
    found = False
    for d in dishes:
        if str(d.get("id")) == str(dish_id):
            d["name"] = req.name.strip()
            d["type"] = req.type.strip().lower()
            d["ingredients"] = req.ingredients.strip()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Plato no encontrado.")
    st_mgr.save_dishes(dishes)
    return {"ok": True, "message": f"¡Plato '{req.name.strip()}' actualizado!", "state": build_application_state(st_mgr)}


@app.delete("/api/dishes/{dish_id}")
def api_delete_dish(dish_id: str):
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    dishes = st_mgr.get_dishes()
    updated = [d for d in dishes if str(d.get("id")) != str(dish_id)]
    if len(updated) == len(dishes):
        raise HTTPException(status_code=404, detail="Plato no encontrado.")
    st_mgr.save_dishes(updated)
    return {"ok": True, "message": "Plato eliminado del catálogo.", "state": build_application_state(st_mgr)}


@app.put("/api/settings")
def api_update_settings(req: SettingsUpdateRequest):
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    saved = st_mgr.get_settings()
    new_settings = {
        "sheet_url": req.sheet_url.strip(),
        "sheet_gid_dishes": req.sheet_gid_dishes.strip(),
        "sheet_gid_freezer": req.sheet_gid_freezer.strip(),
        "calendar_ics_url": req.calendar_ics_url.strip(),
        "smtp_host": req.smtp_host.strip(),
        "smtp_port": int(req.smtp_port),
        "smtp_user": req.smtp_user.strip(),
        "smtp_use_tls": bool(req.smtp_use_tls),
        "recipients": req.recipients.strip(),
        "smtp_password": req.smtp_password.strip() if req.smtp_password.strip() else saved.get("smtp_password", "")
    }
    st_mgr.update_settings(new_settings)
    clear_calendar_cache()
    return {"ok": True, "message": "¡Configuración guardada correctamente!", "state": build_application_state(st_mgr)}


@app.post("/api/email/send")
def api_send_email(req: EmailSendRequest):
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    effective = st_mgr.get_effective_settings(load_external_secrets())
    current_menu = st_mgr.get_current_menu()
    ok, msg = send_weekly_menu_email(effective, current_menu, is_test=req.is_test)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@app.get("/menu_semanal_AyA.ics")
@app.get("/api/calendar.ics")
def api_download_ics():
    st_mgr = StorageManager(filepath=str(BASE_DIR / "menu_app_data.json"))
    _, cycle_desc = get_current_menu_cycle_key(now_madrid())
    current_menu = st_mgr.get_current_menu()
    ics_text = generate_menu_ics(current_menu, f"Menú Semanal AyA ({cycle_desc})")
    return Response(
        content=ics_text.encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="menu_semanal_AyA.ics"'}
    )


# Montar archivos estáticos (SPA / PWA)
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/manifest.json")
def serve_manifest():
    return FileResponse(str(STATIC_DIR / "manifest.json"), media_type="application/manifest+json")


@app.get("/sw.js")
def serve_sw():
    return FileResponse(str(STATIC_DIR / "sw.js"), media_type="application/javascript")


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Menú Semanal AyA API funcionando. Interfaz en construcción."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)

import random
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DAYS_OF_WEEK = [
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
]

import unicodedata

def normalize_text(text: str) -> str:
    """Elimina tildes y convierte a minúsculas para comparaciones flexibles de nombres de platos."""
    if not text:
        return ""
    n = unicodedata.normalize("NFD", str(text).lower().strip())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")

def is_dish_enabled_by_freezer(dish: dict, freezer_data: dict) -> tuple[bool, str]:
    """
    Comprueba si un plato está habilitado según la hoja 'congelador':
    - Si un alimento de la hoja congelador coincide con el plato o sus ingredientes y está en 'no' / False:
      el plato queda DESHABILITADO.
    - Si está en 'si' / True o no figura en la hoja del congelador: queda HABILITADO.
    """
    if not freezer_data:
        return True, "Habilitado"

    items_in_freezer = freezer_data.get("items", {})
    if not items_in_freezer:
        return True, "Habilitado"

    d_name_norm = normalize_text(dish.get("name", ""))
    d_ing_norm = normalize_text(dish.get("ingredients", ""))

    for f_item, status in items_in_freezer.items():
        f_norm = normalize_text(f_item)
        if not f_norm:
            continue

        # Comprobar si el estado es True / Sí o False / No
        is_in_stock = False
        if isinstance(status, bool):
            is_in_stock = status
        elif isinstance(status, int):
            is_in_stock = status > 0
        elif isinstance(status, dict):
            is_in_stock = status.get("portions", 1) > 0
        elif isinstance(status, str):
            is_in_stock = status.lower() in ["si", "sí", "true", "1", "ok"]

        # Si el plato depende de este alimento del congelador y NO hay stock -> deshabilitar
        if (f_norm in d_name_norm) or (f_norm in d_ing_norm):
            if not is_in_stock:
                return False, f"Falta '{f_item}' en el congelador"

    return True, "Habilitado"

def filter_dishes_by_freezer(dishes_list, freezer_data=None):
    """
    Filtra los platos según la hoja 'congelador':
    Solo habilita los platos que no dependan de un alimento marcado como 'no' en el congelador.
    """
    if not freezer_data or not dishes_list:
        return dishes_list

    filtered = []
    for d in dishes_list:
        allowed, _ = is_dish_enabled_by_freezer(d, freezer_data)
        if allowed:
            filtered.append(d)

    return filtered if filtered else dishes_list

def generate_weekly_menu(dishes_list, freezer_data=None):
    """Genera un menú semanal equilibrado (7 días x Comida/Cena) respetando tipos de plato y congelador."""
    if not dishes_list:
        return []

    if freezer_data:
        dishes_list = filter_dishes_by_freezer(dishes_list, freezer_data)

    comidas_pool = [d for d in dishes_list if d.get("type") in ["comida", "ambas"]]
    cenas_pool = [d for d in dishes_list if d.get("type") in ["cena", "ambas"]]

    # Si no hay suficientes platos, duplicamos la lista para evitar errores
    if not comidas_pool:
        comidas_pool = list(dishes_list)
    if not cenas_pool:
        cenas_pool = list(dishes_list)

    # Crear mezclas aleatorias
    shuffled_comidas = list(comidas_pool)
    shuffled_cenas = list(cenas_pool)
    random.shuffle(shuffled_comidas)
    random.shuffle(shuffled_cenas)

    weekly_menu = []
    used_names = set()

    for i, day in enumerate(DAYS_OF_WEEK):
        # Seleccionar comida
        comida = None
        for d in shuffled_comidas:
            if d["name"] not in used_names:
                comida = d
                break
        if not comida:
            comida = random.choice(comidas_pool)
        used_names.add(comida["name"])

        # Seleccionar cena
        cena = None
        for d in shuffled_cenas:
            if d["name"] not in used_names:
                cena = d
                break
        if not cena:
            cena = random.choice(cenas_pool)
        used_names.add(cena["name"])

        weekly_menu.append({
            "day": day,
            "comida": comida,
            "cena": cena
        })

    return weekly_menu

def regenerate_menu_manually(dishes_list, generation_meta):
    """Regenera el menú manualmente si no se ha agotado el límite de 1 vez por semana."""
    manual_used = generation_meta.get("manual_regens_this_week", 0)
    
    if manual_used >= 1:
        return False, None, generation_meta, "Ya has regenerado el menú manualmente esta semana. El límite es 1 regeneración por semana."

    new_menu = generate_weekly_menu(dishes_list)
    new_meta = dict(generation_meta)
    new_meta["manual_regens_this_week"] = manual_used + 1
    new_meta["last_manual_gen_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    return True, new_menu, new_meta, "Menú regenerado con éxito."

def find_alternative_dish(dishes_list, meal_type, current_menu, freezer_data=None):
    """Busca una alternativa válida del mismo tipo (comida/cena/ambas) que no esté en el menú actual respetando el congelador."""
    if freezer_data:
        dishes_list = filter_dishes_by_freezer(dishes_list, freezer_data)

    target_type = "comida" if meal_type.lower() == "comida" else "cena"
    
    # Obtener nombres de platos usados actualmente en el menú
    used_dish_names = set()
    for day in current_menu:
        if day.get("comida"):
            used_dish_names.add(day["comida"].get("name"))
        if day.get("cena"):
            used_dish_names.add(day["cena"].get("name"))

    # Filtrar pool elegible
    eligible_pool = [
        d for d in dishes_list 
        if d.get("type") in [target_type, "ambas"]
    ]

    # Intentar buscar uno no usado actualmente
    unused_pool = [d for d in eligible_pool if d.get("name") not in used_dish_names]

    if unused_pool:
        return random.choice(unused_pool)
    elif eligible_pool:
        return random.choice(eligible_pool)
    else:
        # Fallback si no se encontró ninguno específico
        return random.choice(dishes_list) if dishes_list else None

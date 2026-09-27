import csv
import io
import re
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

SAMPLE_DISHES = [
    {"id": "1", "name": "Huevo y pimiento", "type": "ambas", "ingredients": "Huevos, pimientos, aceite, sal"},
    {"id": "2", "name": "Judías verdes y patatas cocidas", "type": "ambas", "ingredients": "Judías verdes, patatas, aceite de oliva, vinagre"},
    {"id": "3", "name": "Tortilla francesa y ensalada", "type": "cena", "ingredients": "Huevos, lechuga, tomate, aceite, sal"},
    {"id": "4", "name": "Lentejas", "type": "comida", "ingredients": "Lentejas, zanahoria, patata, puerro, pimentón"},
    {"id": "5", "name": "Tortitas aguacate", "type": "cena", "ingredients": "Tortitas, aguacate, tomate, queso fresco"},
    {"id": "6", "name": "Puré puerros y calabacín", "type": "cena", "ingredients": "Puerros, calabacín, patata, aceite, quesito"},
    {"id": "7", "name": "Ensalada de pasta", "type": "comida", "ingredients": "Pasta, atún, maíz, tomate, aceitunas"},
    {"id": "8", "name": "Ensalada pimientos y Melva", "type": "cena", "ingredients": "Pimientos asados, melva en aceite, cebolla, vinagre"},
    {"id": "9", "name": "Pollo/Lomo y gnocchi", "type": "ambas", "ingredients": "Filetes de pollo o lomo, gnocchis, salsa al gusto"},
    {"id": "10", "name": "Ensalada de garbanzos", "type": "comida", "ingredients": "Garbanzos cocidos, pimiento, tomate, cebolla, atún"},
    {"id": "11", "name": "Ensalada de lentejas", "type": "comida", "ingredients": "Lentejas cocidas, zanahoria, pimiento, vinagreta"},
    {"id": "12", "name": "Patatas con carne", "type": "comida", "ingredients": "Patatas, carne de ternera troceada, sofrito, caldo"},
    {"id": "13", "name": "Garbanzos y calabacín al curry", "type": "comida", "ingredients": "Garbanzos, calabacín, cebolla, curry, leche de coco"},
    {"id": "14", "name": "Fajitas de pollo", "type": "cena", "ingredients": "Tortillas de trigo, tiras de pollo, pimientos, cebolla, especias fajitas"},
    {"id": "15", "name": "Pollo asado", "type": "comida", "ingredients": "Pollo entero o cuartos, patatas, limón, romero, ajo"},
    {"id": "16", "name": "Pollo al curry", "type": "comida", "ingredients": "Pechuga de pollo, cebolla, curry, nata o leche de coco, arroz"},
    {"id": "17", "name": "Pasta boloñesa", "type": "comida", "ingredients": "Pasta, carne picada, tomate frito, cebolla, orégano"},
    {"id": "18", "name": "Muslitos guisados", "type": "comida", "ingredients": "Muslos de pollo, zanahoria, guisantes, patata, caldo"},
    {"id": "19", "name": "Chistorra y puré de patata", "type": "ambas", "ingredients": "Chistorra a la plancha, puré de patata casero"},
    {"id": "20", "name": "Puchero", "type": "comida", "ingredients": "Garbanzos, ternera, pollo, tocino, fideos o arroz"},
    {"id": "21", "name": "Pisto con huevo", "type": "comida", "ingredients": "Calabacín, pimiento, tomate, cebolla, huevos fritos o escalfados"},
    {"id": "22", "name": "Noodles con verdura", "type": "comida", "ingredients": "Noodles, zanahoria, calabacín, salsa de soja, sésamo"},
    {"id": "23", "name": "Salmón con boniato/patatas y brócoli", "type": "comida", "ingredients": "Lomo de salmón, boniato o patata al horno, brócoli al vapor"},
    {"id": "24", "name": "Gyoza", "type": "cena", "ingredients": "Gyozas de carne o verdura, salsa de soja y vinagre de arroz"},
    {"id": "25", "name": "Fideos chinos", "type": "comida", "ingredients": "Fideos chinos, verduras variadas, pollo o gambas, salsa de soja"},
    {"id": "26", "name": "Tuna melt", "type": "cena", "ingredients": "Pan de molde tostado, atún, mayonesa, queso fundido"},
    {"id": "27", "name": "Sandwich mixto", "type": "cena", "ingredients": "Pan de molde, jamón york, queso fundido, mantequilla"},
    {"id": "28", "name": "Ensaladilla", "type": "ambas", "ingredients": "Patatas, zanahoria, atún, guisantes, huevos cocidos, mayonesa"},
    {"id": "29", "name": "Pasta cherrys feta", "type": "comida", "ingredients": "Pasta, tomates cherry asados, queso feta, albahaca"},
    {"id": "30", "name": "Fajitas falafel", "type": "cena", "ingredients": "Tortillas de trigo, falafel, lechuga, tomate, salsa de yogur"},
    {"id": "31", "name": "Falafel con yogur", "type": "cena", "ingredients": "Falafel crujiente, ensalada mixta, salsa de yogur con menta"},
    {"id": "32", "name": "Croquetas", "type": "ambas", "ingredients": "Croquetas caseras de jamón o pollo, ensalada de acompañamiento"},
    {"id": "33", "name": "Albóndigas", "type": "comida", "ingredients": "Albóndigas de carne en salsa de tomate o salsa española, patatas"},
    {"id": "34", "name": "Ensalada atún, huevo y patata", "type": "ambas", "ingredients": "Patata cocida, atún, huevos cocidos, cebolla, aceite, vinagre"},
    {"id": "35", "name": "Espinacas con garbanzos", "type": "comida", "ingredients": "Garbanzos cocidos, espinacas, ajo, pimentón, comino"},
    {"id": "36", "name": "Gulas con gambas", "type": "cena", "ingredients": "Gulas, gambas peladas, ajo laminado, guindilla, aceite de oliva"}
]

def normalize_sheet_url(url_or_id: str, default_gid: str = None) -> str:
    """Transforma cualquier enlace o ID de Google Sheet a la URL pública de exportación CSV."""
    if not url_or_id:
        return ""
    url_or_id = url_or_id.strip()
    
    # Extraer ID y GID si es una URL de Google Sheets
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url_or_id)
    gid_match = re.search(r'[#&?]gid=([0-9]+)', url_or_id)
    gid = gid_match.group(1) if gid_match else default_gid
    gid_param = f"&gid={gid}" if gid else ""

    if match:
        sheet_id = match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_param}"
    
    # Si parece un ID simple de Google Sheets (sin slashes)
    if not url_or_id.startswith("http") and len(url_or_id) > 15:
        return f"https://docs.google.com/spreadsheets/d/{url_or_id}/export?format=csv{gid_param}"
    
    # Si ya contiene export?format=csv
    if "export?format=csv" in url_or_id:
        if gid_match and "gid=" not in url_or_id:
            return f"{url_or_id}{gid_param}"
        return url_or_id
        
    return url_or_id

def normalize_meal_type(raw_type: str) -> str:
    """Normaliza el tipo de plato a 'comida', 'cena' o 'ambas'."""
    if not raw_type:
        return "ambas"
    t = str(raw_type).strip().lower()
    if t in ["comida", "almuerzo", "comidas"]:
        return "comida"
    elif t in ["cena", "cenas"]:
        return "cena"
    elif t in ["ambas", "ambos", "comida/cena", "comida y cena", "todos"]:
        return "ambas"
    return "ambas"

def fetch_dishes_from_csv(sheet_url_or_id: str, gid: str = "83672031"):
    """Descarga y parsea el CSV desde Google Sheets con la estructura requerida."""
    export_url = normalize_sheet_url(sheet_url_or_id, default_gid=gid)
    if not export_url:
        logger.warning("URL de Google Sheets no configurada. Usando platos de muestra.")
        return SAMPLE_DISHES, "Sin URL configurada (usando platos de muestra)."

    try:
        req = urllib.request.Request(
            export_url,
            headers={"User-Agent": "Mozilla/5.0 (Android; Mobile; rv:109.0)"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content_bytes = response.read()
        
        # Detectar codificación
        content_text = content_bytes.decode('utf-8-sig', errors='replace')
        f = io.StringIO(content_text)
        reader = csv.DictReader(f)
        
        dishes = []
        for idx, row in enumerate(reader, start=1):
            # Normalizar nombres de columnas ignorando mayúsculas y espacios
            normalized_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            
            dish_id = normalized_row.get("id") or str(idx)
            name = (
                normalized_row.get("plato") or 
                normalized_row.get("nombre") or 
                normalized_row.get("name") or 
                ""
            ).strip()
            raw_type = normalized_row.get("tipo", "ambas")
            ingredients = normalized_row.get("ingredientes", "")
            
            if name:
                dishes.append({
                    "id": str(dish_id),
                    "name": name,
                    "type": normalize_meal_type(raw_type),
                    "ingredients": ingredients
                })
        
        if not dishes:
            logger.warning("El CSV descargado no contiene platos válidos. Usando platos de muestra.")
            return SAMPLE_DISHES, "El CSV no contenía platos válidos (usando platos de muestra)."

        logger.info(f"Se han cargado con éxito {len(dishes)} platos desde Google Sheets.")
        return dishes, f"Cargados {len(dishes)} platos correctamente."

    except Exception as e:
        logger.error(f"Error descargando el CSV desde Google Sheets: {e}")
        return SAMPLE_DISHES, f"Error de conexión: {str(e)} (usando platos de muestra)."

FREEZER_SHEET_GID = "797240193"

def normalize_freezer_sheet_url(url_or_id: str, gid: str = FREEZER_SHEET_GID) -> str:
    """Transforma el enlace o ID de Google Sheets a la URL de exportación CSV para la pestaña congelador."""
    if not url_or_id:
        return ""
    url_or_id = url_or_id.strip()
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url_or_id)
    if match:
        sheet_id = match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    if not url_or_id.startswith("http") and len(url_or_id) > 15:
        return f"https://docs.google.com/spreadsheets/d/{url_or_id}/export?format=csv&gid={gid}"
    return url_or_id

def fetch_freezer_from_csv(sheet_url_or_id: str, gid: str = FREEZER_SHEET_GID):
    """Descarga y parsea la hoja 'congelador' desde Google Sheets."""
    export_url = normalize_freezer_sheet_url(sheet_url_or_id, gid)
    if not export_url:
        return {}, "Sin URL configurada para el congelador."

    try:
        req = urllib.request.Request(
            export_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content_bytes = response.read()

        content_text = content_bytes.decode('utf-8-sig', errors='replace')
        f = io.StringIO(content_text)
        reader = csv.DictReader(f)

        freezer_items = {}
        for row in reader:
            normalized_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            dish_name = (
                normalized_row.get("plato") or 
                normalized_row.get("nombre") or 
                normalized_row.get("alimento") or 
                ""
            ).strip()

            val = ""
            for k, v in normalized_row.items():
                if "congelador" in k or "disponible" in k or "hay" in k:
                    val = v.lower()
                    break
            if not val:
                val = normalized_row.get("estado", "").lower()

            is_available = val in ["si", "sí", "yes", "true", "1", "ok"]
            if dish_name:
                freezer_items[dish_name] = is_available

        logger.info(f"Se han cargado {len(freezer_items)} items desde la hoja 'congelador'.")
        return freezer_items, f"Cargados {len(freezer_items)} elementos del congelador correctamente."

    except Exception as e:
        logger.error(f"Error descargando hoja congelador: {e}")
        return {}, f"Error al cargar hoja congelador: {str(e)}"

def get_sample_dishes():
    return SAMPLE_DISHES

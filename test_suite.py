import unittest
import os
import json
from datetime import datetime, timedelta

from storage_manager import StorageManager
from csv_loader import normalize_sheet_url, normalize_meal_type, SAMPLE_DISHES
from menu_generator import generate_weekly_menu, regenerate_menu_manually, find_alternative_dish, filter_dishes_by_freezer
from veto_manager import apply_veto, can_user_veto, reset_weekly_vetos, get_veto_window_status, VETO_LIMIT_PER_PERSON
from coupon_manager import create_coupon, add_coupon, toggle_coupon_status, check_expiration_warning, get_expiring_coupons_alert
from emailer import generate_menu_html, generate_menu_text

class TestAlvaroMenuApp(unittest.TestCase):
    
    def setUp(self):
        self.test_json = "test_menu_data.json"
        if os.path.exists(self.test_json):
            os.remove(self.test_json)
        self.storage = StorageManager(filepath=self.test_json)

    def tearDown(self):
        if os.path.exists(self.test_json):
            os.remove(self.test_json)

    def test_url_normalization(self):
        raw_url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit?usp=sharing"
        expected = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export?format=csv"
        self.assertEqual(normalize_sheet_url(raw_url), expected)

        bare_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        self.assertEqual(normalize_sheet_url(bare_id), expected)

    def test_meal_type_normalization(self):
        self.assertEqual(normalize_meal_type("Comida"), "comida")
        self.assertEqual(normalize_meal_type("Cena"), "cena")
        self.assertEqual(normalize_meal_type("Comida y Cena"), "ambas")

    def test_menu_generation(self):
        menu = generate_weekly_menu(SAMPLE_DISHES)
        self.assertEqual(len(menu), 7)
        for day_entry in menu:
            self.assertIn("day", day_entry)
            self.assertIn("comida", day_entry)
            self.assertIn("cena", day_entry)

    def test_manual_regeneration_limit(self):
        meta = {"manual_regens_this_week": 0}
        success, menu1, meta1, msg1 = regenerate_menu_manually(SAMPLE_DISHES, meta)
        self.assertTrue(success)
        self.assertEqual(meta1["manual_regens_this_week"], 1)

        # Intento de 2ª regeneración manual debe ser bloqueado
        success2, menu2, meta2, msg2 = regenerate_menu_manually(SAMPLE_DISHES, meta1)
        self.assertFalse(success2)
        self.assertIn("límite", msg2.lower())

    def test_veto_system_quota_and_substitution(self):
        menu = generate_weekly_menu(SAMPLE_DISHES)
        vetos_state = {"alvaro_used": 0, "pareja_used": 0, "history": []}
        
        # 1er veto de Álvaro
        ok1, menu1, vetos1, msg1, new_dish1 = apply_veto("Álvaro", "Lunes", "Comida", menu, SAMPLE_DISHES, vetos_state)
        self.assertTrue(ok1)
        self.assertEqual(vetos1["alvaro_used"], 1)

        # 2º veto de Álvaro
        ok2, menu2, vetos2, msg2, new_dish2 = apply_veto("Álvaro", "Martes", "Cena", menu1, SAMPLE_DISHES, vetos1)
        self.assertTrue(ok2)
        self.assertEqual(vetos2["alvaro_used"], 2)

        # 3er veto de Álvaro (Debe ser BLOQUEADO por límite de 2)
        ok3, menu3, vetos3, msg3, new_dish3 = apply_veto("Álvaro", "Miércoles", "Comida", menu2, SAMPLE_DISHES, vetos2)
        self.assertFalse(ok3)
        self.assertEqual(vetos3["alvaro_used"], 2)
        self.assertIn("agotado", msg3.lower())

        # Veto para Pareja debe seguir funcionando (0/2 usados)
        ok_pareja, menu4, vetos4, msg4, new_dish_p = apply_veto("Pareja", "Jueves", "Comida", menu3, SAMPLE_DISHES, vetos3)
        self.assertTrue(ok_pareja)
        self.assertEqual(vetos4["pareja_used"], 1)

    def test_veto_reset_on_saturday(self):
        vetos_state = {"alvaro_used": 2, "pareja_used": 2}
        reseted = reset_weekly_vetos(vetos_state)
        self.assertEqual(reseted["alvaro_used"], 0)
        self.assertEqual(reseted["pareja_used"], 0)

    def test_coupon_expiration_alerts(self):
        today = datetime.now().date()
        exp_soon = (today + timedelta(days=3)).strftime("%Y-%m-%d")
        exp_late = (today + timedelta(days=30)).strftime("%Y-%m-%d")
        
        c1 = create_coupon("Álvaro", "2x1 Pizza", "Telepizza", exp_soon, "Urgente")
        c2 = create_coupon("Pareja", "Cena Elegante", "DiverXO", exp_late, "Tranquilo")

        coupons = [c1, c2]
        alerts = get_expiring_coupons_alert(coupons, threshold_days=7)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["coupon"]["title"], "2x1 Pizza")

    def test_email_formatting(self):
        menu = generate_weekly_menu(SAMPLE_DISHES)
        html = generate_menu_html(menu)
        text = generate_menu_text(menu)
        self.assertIn("Lunes", html)
        self.assertIn("Domingo", text)
        self.assertIn("Álvaro", html)

    def test_veto_window_schedule(self):
        # Sábado a las 14:00 -> Abierto
        sat = datetime(2026, 9, 26, 14, 0)
        is_open, msg, dt_ref = get_veto_window_status(sat)
        self.assertTrue(is_open)
        self.assertIn("16:00", msg)

        # Domingo a las 15:59 -> Abierto
        sun_open = datetime(2026, 9, 27, 15, 59)
        is_open, msg, dt_ref = get_veto_window_status(sun_open)
        self.assertTrue(is_open)

        # Domingo a las 16:01 -> Cerrado
        sun_closed = datetime(2026, 9, 27, 16, 1)
        is_open, msg, dt_ref = get_veto_window_status(sun_closed)
        self.assertFalse(is_open)
        self.assertIn("Cerrado", msg)

        # Miércoles a las 12:00 -> Cerrado
        wed_closed = datetime(2026, 9, 30, 12, 0)
        is_open, msg, dt_ref = get_veto_window_status(wed_closed)
        self.assertFalse(is_open)

    def test_freezer_dish_availability(self):
        # Si Falafel está marcado como False en el congelador, sus platos quedan deshabilitados
        freezer_data = {
            "items": {"Falafel": False}
        }
        filtered = filter_dishes_by_freezer(SAMPLE_DISHES, freezer_data)
        names = [d["name"] for d in filtered]
        self.assertNotIn("Fajitas falafel", names)
        self.assertNotIn("Falafel con yogur", names)

        # Si Falafel está en existencias (True o 'si'), se habilita en el menú
        freezer_data["items"]["Falafel"] = True
        filtered2 = filter_dishes_by_freezer(SAMPLE_DISHES, freezer_data)
        names2 = [d["name"] for d in filtered2]
        self.assertIn("Fajitas falafel", names2)
        self.assertIn("Falafel con yogur", names2)

if __name__ == "__main__":
    unittest.main()

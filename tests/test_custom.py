import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsxwl.custom import dict_to_form, form_to_dict  # noqa: E402
from fsxwl.metar import parse_metar, to_simconnect  # noqa: E402

FORM = {"wind": {"dir": 250, "kt": 18, "gust_kt": 30, "var": 30}, "vis_m": 3000,
        "wx": {"intensity": "+", "type": "TSRA"},
        "clouds": [{"cover": "OVC", "base_ft": 8000}, {"cover": "BKN", "base_ft": 3500, "cb": True}],
        "temp": 24, "dew": 20, "qnh": 1002}


class TestCustom(unittest.TestCase):
    def sim(self, form, icao="GLOB"):
        return to_simconnect(icao, form_to_dict(form), include_type=False)

    def test_full_form_builds_simconnect_metar(self):
        m = self.sim(FORM).split()
        self.assertEqual(m[0], "GLOB")
        self.assertEqual(m[2:], ["25018G30KT", "220V280", "2SM", "+TSRA", "BKN035CB", "OVC080", "24/20", "Q1002"])

    def test_north_wind_is_360_and_calm_is_00000(self):
        self.assertIn("36012KT", self.sim({"wind": {"dir": 0, "kt": 12}}))
        self.assertIn("00000KT", self.sim({"wind": {"dir": 0, "kt": 0}}))

    def test_variable_wind_and_no_weather(self):
        m = self.sim({"wind": {"dir": None, "kt": 4}, "wx": {"type": ""}, "clouds": []})
        self.assertIn("VRB04KT", m)
        self.assertIn("SKC", m)

    def test_values_are_clamped_and_junk_dropped(self):
        d = form_to_dict({"wind": {"dir": "abc", "kt": 999, "gust_kt": 5}, "temp": 10, "dew": 30,
                          "qnh": 5, "wx": {"type": "XX'; DROP"}, "clouds": [{"cover": "LOTS"}] * 5})
        self.assertEqual(d["wind"]["kt"], 150)
        self.assertIsNone(d["wind"]["gust_kt"])      # a gust below the mean wind is dropped
        self.assertEqual(d["dew"], 10)               # dew point never above temperature
        self.assertEqual(d["qnh_hpa"], 900)
        self.assertEqual(d["wx"], [])
        self.assertEqual(d["clouds"], [])

    def test_fog_takes_no_intensity(self):
        self.assertEqual(form_to_dict({"wx": {"intensity": "+", "type": "FG"}})["wx"], ["FG"])

    def test_real_metar_round_trip(self):
        f = dict_to_form(parse_metar("LERS 251030Z 28018G28KT 250V310 9999 -RA FEW030 BKN040 10/06 Q1012"))
        self.assertEqual(f["wind"], {"dir": 280, "kt": 18, "gust_kt": 28, "var": 30})
        self.assertEqual(f["wx"], {"intensity": "-", "type": "RA"})
        self.assertEqual([c["cover"] for c in f["clouds"]], ["FEW", "BKN"])
        m = self.sim(f, "LERS")
        self.assertIn("28018G28KT 250V310", m)
        self.assertIn("-RA FEW030 BKN040 10/06 Q1012", m)


if __name__ == "__main__":
    unittest.main()

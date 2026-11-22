import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsxwl.metar import parse_metar, to_simconnect, summary_es, condition, weather_info  # noqa: E402

NOW = datetime(2026, 11, 20, 10, 5, tzinfo=timezone.utc)


def conv(raw, **kw):
    d = parse_metar(raw)
    return d, to_simconnect(d["icao"], d, now=NOW, **kw)


class TestMetar(unittest.TestCase):
    def test_condition_categories(self):
        cases = {
            "LEMD 201000Z 27012KT CAVOK 14/05 Q1021": "clear",
            "LEMD 201000Z 27012KT 9999 FEW030 14/05 Q1021": "few",
            "LEMD 201000Z 27012KT 9999 FEW030 BKN080 14/05 Q1021": "cloudy",
            "EGLL 201000Z 22015KT 6000 -RA OVC012 10/09 Q1002": "rain",
            "EGLL 201000Z 22015KT 6000 -SHRA SCT020CB 10/09 Q1002": "showers",
            "KJFK 201000Z 18020G35KT 2SM +TSRA BKN015CB 22/20 A2970": "thunder",
            "ENGM 201000Z 01005KT 1500 SN OVC008 M03/M04 Q0998": "snow",
            "LEBL 201000Z 00000KT 0200 FG VV001 08/08 Q1025": "fog",
            "LEBL 201000Z 00000KT 4000 BR NSC 08/07 Q1025": "mist",
            "LEBL 201000Z 00000KT 9999 VCSH FEW040 18/10 Q1025": "few",
        }
        for raw, exp in cases.items():
            self.assertEqual(condition(parse_metar(raw)), exp, raw)

    def test_weather_info(self):
        w = weather_info(parse_metar("EGLL 201000Z 22015G28KT 6000 -RA OVC012 10/09 Q1002"), "en")
        self.assertEqual(w["cond"], "rain")
        self.assertEqual(w["text"], "Rain")
        self.assertEqual(w["wind"], {"dir": 220, "kt": 15, "gust_kt": 28})
        self.assertEqual((w["temp"], w["dew"], w["qnh_hpa"], w["vis_m"]), (10, 9, 1002, 6000))

    def test_europe_icao(self):
        d, s = conv("LEMD 201000Z 27012G22KT 240V300 9999 FEW030 SCT080 14/05 Q1021 NOSIG")
        self.assertEqual(d["wind"], {"dir": 270, "kt": 12, "gust_kt": 22})
        self.assertEqual(d["wind_var"], (240, 300))
        self.assertEqual(d["qnh_hpa"], 1021)
        self.assertEqual(s, "LEMD METAR 201005Z 27012G22KT 240V300 10KM FEW030 SCT080 14/05 Q1021")

    def test_us_statute_miles_and_altimeter(self):
        d, s = conv("KSEA 030405Z 27007KT 15SM SKC 17/13 A2992")
        self.assertEqual(d["qnh_hpa"], 1013)
        self.assertEqual(s, "KSEA METAR 201005Z 27007KT 24KM SKC 17/13 Q1013")

    def test_thunderstorm_cb(self):
        d, s = conv("KSEA 030405Z COR 27015KT 7SM +TSRA BKN055CB 30/17 A2974")
        self.assertEqual(d["wx"], ["+TSRA"])
        self.assertIn("+TSRA", s)
        self.assertIn("BKN055CB", s)
        self.assertIn(" 11KM ", s)  # 7 SM = 11.3 km

    def test_negative_temps_and_fraction_visibility(self):
        d, s = conv("CYYZ 201000Z 31010KT 1 1/2SM -SN BKN008 OVC015 M05/M07 A2985")
        self.assertEqual(d["temp"], -5)
        self.assertEqual(d["dew"], -7)
        self.assertEqual(d["vis_m"], int(1.5 * 1609.344))
        self.assertIn("-05/-07", s)
        self.assertIn("-SN", s)
        self.assertIn("2SM", s)  # 1.5 SM is rounded

    def test_low_visibility_fraction(self):
        _, s = conv("EGLL 201000Z 00000KT 0400 FG VV002 08/08 Q1030")
        self.assertIn(" FG ", s)
        self.assertIn("OVC002", s)
        self.assertIn(" 1/4SM ", s)  # 400 m = 0.249 SM -> 2/8 = 1/4

    def test_cavok(self):
        d, s = conv("LFPG 201000Z VRB02KT CAVOK 12/08 Q1018")
        self.assertTrue(d["cavok"])
        self.assertIn("VRB02KT", s)
        self.assertIn("SKC", s)
        self.assertIn("10KM", s)

    def test_mps_and_kmh_units(self):
        d = parse_metar("UUEE 201000Z 18005MPS 9999 BKN020 05/03 Q1010")
        self.assertEqual(d["wind"]["kt"], 10)
        d = parse_metar("ZZZZ 201000Z 18020KMH 9999 SCT020 05/03 Q1010")
        self.assertEqual(d["wind"]["kt"], 11)

    def test_ignores_rmk_and_trend(self):
        d = parse_metar("LEBL 201000Z 05008KT 9999 SCT020 15/10 Q1019 TEMPO 4000 RA RMK AO2")
        self.assertEqual(d["wx"], [])
        self.assertEqual(d["qnh_hpa"], 1019)

    def test_max_cloud_layers(self):
        _, s = conv("KJFK 201000Z 18010KT 10SM FEW010 SCT020 BKN030 OVC040 10/05 A3000")
        self.assertEqual(s.count("FEW") + s.count("SCT") + s.count("BKN") + s.count("OVC"), 3)
        self.assertNotIn("OVC040", s)

    def test_unsupported_weather_dropped(self):
        d = parse_metar("KDEN 201000Z 18010KT 10SM BCFG SCT100 10/05 A3000")
        _, s = conv("KDEN 201000Z 18010KT 10SM BCFG SCT100 10/05 A3000")
        self.assertNotIn("BCFG", s)

    def test_no_type_keyword_option(self):
        _, s = conv("KSEA 030405Z 27007KT 15SM SKC 17/13 A2992", include_type=False)
        self.assertTrue(s.startswith("KSEA 201005Z"))

    def test_missing_data_does_not_crash(self):
        d = parse_metar("XXXX 201000Z AUTO /////KT //// ///// 15/ Q////")
        s = to_simconnect("XXXX", d, now=NOW)
        self.assertTrue(s.startswith("XXXX METAR 201005Z"))

    def test_summary_spanish(self):
        d = parse_metar("LEMD 201000Z 27012G22KT 9999 FEW030 14/05 Q1021")
        t = summary_es(d)
        self.assertIn("Viento 270° a 12 kt", t)
        self.assertIn("QNH 1021", t)

    def test_length_limit(self):
        _, s = conv("KORD 201000Z 18010G35KT 190V250 1/2SM +TSRA BKN005CB OVC010 20/19 A2980")
        self.assertLess(len(s), 200)


if __name__ == "__main__":
    unittest.main()

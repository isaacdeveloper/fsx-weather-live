import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsxwl import net  # noqa: E402
from fsxwl.app import App, DEFAULTS, make_handler  # noqa: E402
from fsxwl.i18n import STR, get_lang, set_lang  # noqa: E402

FAKE = [
    {"icao": "LEMD", "raw": "LEMD 201000Z 27012G22KT 9999 FEW030 14/05 Q1021", "lat": 40.47, "lon": -3.56,
     "elev_m": 610, "name": "Madrid", "dist_km": 0.0},
    {"icao": "LETO", "raw": "LETO 201000Z 24008KT 9999 SCT040 13/04 Q1021", "lat": 40.49, "lon": -3.45,
     "elev_m": 600, "name": "Torrejon", "dist_km": 9.0},
]


class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        net.metars_near = lambda lat, lon, r, n: [dict(s) for s in FAKE]
        cls.tmp = tempfile.mkdtemp()
        cfg = dict(DEFAULTS, port=18765, simconnect_dll="no-existe.dll")
        cls.app = App(cls.tmp, cfg)
        cls.posted = []
        cls.app.sim.post = lambda fn, *a: cls.posted.append((fn.__name__, a))
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 18765), make_handler(cls.app))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.app.refresh()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:18765" + path) as r:
            return r.read()

    def post(self, path, body, headers=None):
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request("http://127.0.0.1:18765" + path, json.dumps(body).encode(), h, method="POST")
        return urllib.request.urlopen(req)

    def test_state_has_converted_stations(self):
        st = json.loads(self.get("/api/state"))
        self.assertEqual(len(st["stations"]), 2)
        s = st["stations"][0]
        self.assertTrue(s["sim_metar"].startswith("LEMD "))
        self.assertNotIn("METAR", s["sim_metar"])  # FSX rejects it (WEATHER_INVALID_METAR)
        self.assertIn("Viento 270° a 12 kt", s["summary"])
        self.assertFalse(st["inject"]["enabled"])

    def test_index_served(self):
        self.assertIn(b"FSX Weather Live", self.get("/"))

    def test_post_without_header_is_forbidden(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.post("/api/inject", {"enabled": True})
        self.assertEqual(c.exception.code, 403)
        self.assertFalse(self.app.inject)

    def test_post_from_foreign_origin_is_forbidden(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.post("/api/inject", {"enabled": True}, {"X-FSXWL": "1", "Origin": "http://evil.example"})
        self.assertEqual(c.exception.code, 403)

    def test_inject_toggle(self):
        self.posted.clear()
        self.post("/api/inject", {"enabled": True}, {"X-FSXWL": "1", "Origin": "http://localhost:18765"})
        self.assertTrue(self.app.inject)
        self.assertIn("cmd_enable_custom", [p[0] for p in self.posted])
        self.post("/api/inject", {"enabled": False}, {"X-FSXWL": "1"})
        self.assertFalse(self.app.inject)
        self.assertIn("cmd_restore_global", [p[0] for p in self.posted])

    def test_diag_requires_sim_and_header(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/diag", {})
        r = json.loads(self.post("/api/diag", {}, {"X-FSXWL": "1"}).read())
        self.assertIn("no está conectado", r["msg"])

    def test_diag_launches_with_sim(self):
        import time as _t
        set_lang("en")
        self.posted.clear()
        self.app.sim.connected = True
        self.app.sim.pos = {"lat": 40.0, "lon": -3.0, "alt_ft": 0, "hdg": 0, "gs_kt": 0, "t": _t.time()}
        try:
            r = json.loads(self.post("/api/diag", {}, {"X-FSXWL": "1"}).read())
            self.assertIn("started", r["msg"])
            self.assertEqual(self.posted[0][0], "cmd_diag")
            self.assertEqual(self.posted[0][1][3], "LEMD")
        finally:
            self.app.sim.connected = False
            self.app.sim.pos = None

    def test_search_icao_uses_metars_by_ids(self):
        net.metars_by_ids = lambda ids: [dict(FAKE[1])]
        r = json.loads(self.get("/api/search?q=LETO"))
        self.assertEqual(r["name"], "LETO")
        self.assertEqual(len(r["stations"]), 1)

    def test_area_returns_stations_in_view_with_weather(self):
        calls = []
        net.metars_in_bbox = lambda *box: calls.append(box) or [dict(s) for s in FAKE] + [
            {"icao": "KJFK", "raw": "KJFK 201000Z 31010KT 10SM FEW250 05/M05 A3012", "lat": 40.64, "lon": -73.78,
             "elev_m": 4, "name": "New York JFK Intl", "dist_km": 0.0}]
        self.app.area_cache.clear()
        r = json.loads(self.get("/api/area?s=39&w=-5&n=42&e=-2&cols=20&rows=20"))
        self.assertEqual(sorted(s["icao"] for s in r["stations"]), ["LEMD", "LETO"])
        self.assertEqual(r["total"], 2)
        self.assertIn("weather", r["stations"][0])
        self.get("/api/area?s=39.1&w=-4.9&n=41.9&e=-2.1")  # small pan: served from cache
        self.assertEqual(len(calls), 1)

    def test_area_bad_bbox(self):
        for q in ("s=1&w=2&n=3", "s=a&w=1&n=2&e=3", "s=nan&w=1&n=2&e=3"):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.get("/api/area?" + q)
            self.assertEqual(cm.exception.code, 400)

    def test_area_crossing_antimeridian(self):
        net.metars_in_bbox = lambda *box: [
            {"icao": "NFFN", "raw": "NFFN 201000Z 09010KT 9999 FEW020 28/22 Q1010", "lat": -17.75, "lon": 177.44,
             "elev_m": 18, "name": "Nadi Intl", "dist_km": 0.0},
            {"icao": "NSTU", "raw": "NSTU 201000Z 09010KT 9999 FEW020 28/22 Q1010", "lat": -14.33, "lon": -170.71,
             "elev_m": 10, "name": "Pago Pago", "dist_km": 0.0}]
        self.app.area_cache.clear()
        # Leaflet reports east > 180 after panning past the date line.
        r = json.loads(self.get("/api/area?s=-25&w=170&n=-10&e=195"))
        self.assertEqual(sorted(s["icao"] for s in r["stations"]), ["NFFN", "NSTU"])

    def test_search_empty_and_failure(self):
        self.assertIn("error", json.loads(self.get("/api/search?q=")))
        net.geocode = lambda q: (_ for _ in ()).throw(RuntimeError("no network"))
        self.assertIn("error", json.loads(self.get("/api/search?q=calle%20falsa")))

    def test_fetch_failure_keeps_previous_data(self):
        def boom(*a):
            raise OSError("no network")
        old = net.metars_near
        net.metars_near = boom
        try:
            self.app.refresh()
            st = json.loads(self.get("/api/state"))
            self.assertEqual(len(st["stations"]), 2)
            self.assertIn("No se pudo descargar", st["fetch_error"])
        finally:
            net.metars_near = old

    def tearDown(self):
        set_lang("es")

    def test_lang_endpoint_switches_texts(self):
        H = {"X-FSXWL": "1"}
        self.assertEqual(json.loads(self.get("/api/state"))["lang"], "es")
        self.post("/api/lang", {"lang": "en"}, H)
        st = json.loads(self.get("/api/state"))
        self.assertEqual(st["lang"], "en")
        self.assertIn("Wind 270° at 12 kt", st["stations"][0]["summary"])
        self.assertNotIn("_d", st["stations"][0])
        r = json.loads(self.post("/api/diag", {}, H).read())
        self.assertIn("not connected", r["msg"])
        self.assertIn("Enter an address", json.loads(self.get("/api/search?q="))["error"])

    def test_lang_endpoint_rejects_unknown_and_foreign(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.post("/api/lang", {"lang": "fr"}, {"X-FSXWL": "1"})
        self.assertEqual(c.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.post("/api/lang", {"lang": "en"})
        self.assertEqual(c.exception.code, 403)
        self.assertEqual(get_lang(), "es")


class TestI18n(unittest.TestCase):
    def tearDown(self):
        set_lang("es")

    def test_every_key_has_both_languages(self):
        for k, v in STR.items():
            self.assertEqual(set(v), {"es", "en"}, k)
            self.assertTrue(v["es"] and v["en"], k)

    def test_placeholders_match_between_languages(self):
        import string
        f = string.Formatter()
        for k, v in STR.items():
            names = lambda x: {n for _, n, _, _ in f.parse(x) if n}
            self.assertEqual(names(v["es"]), names(v["en"]), k)

    def test_unknown_language_falls_back_to_es(self):
        self.assertEqual(set_lang("xx"), "es")

    def test_summary_en_and_es(self):
        from fsxwl.metar import parse_metar, summary
        d = parse_metar("LEMD 201000Z 27012G22KT 9999 FEW030 14/05 Q1021")
        self.assertIn("gusts 22", summary(d, "en"))
        self.assertIn("rachas 22", summary(d, "es"))
        self.assertIn("Clouds:", summary(d, "en"))


class TestNetClean(unittest.TestCase):
    def test_clean_tolerates_missing_fields(self):
        res = net._clean([{"icaoId": "A"}, {"icaoId": "LEMD", "rawOb": "x", "lat": 1, "lon": 2}, "basura"])
        self.assertEqual([r["icao"] for r in res], ["LEMD"])
        self.assertEqual(net._clean(None), [])

    def test_thin_grid_one_per_cell_prefers_intl(self):
        st = [{"icao": "AAAA", "name": "Small field", "lat": 0.1, "lon": 0.1},
              {"icao": "BBBB", "name": "Big Intl", "lat": 0.2, "lon": 0.2},
              {"icao": "CCCC", "name": "", "lat": 9.9, "lon": 9.9}]
        res = net.thin_grid(st, 0, 0, 10, 10, 2, 2)
        self.assertEqual(sorted(s["icao"] for s in res), ["BBBB", "CCCC"])


if __name__ == "__main__":
    unittest.main()

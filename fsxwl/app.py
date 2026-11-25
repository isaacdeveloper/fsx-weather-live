"""Application: METAR scheduler, shared state and local web server."""
import json
import math
import os
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import net
from .i18n import SUPPORTED, get_lang, set_lang, t
from .metar import parse_metar, to_simconnect, summary, weather_info
from .overlay import Overlay
from .sim import Sim

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")

DEFAULTS = {
    "language": "en",   # "en" or "es" (switchable from the web UI)
    "port": 8080,
    "update_minutes": 5,
    "radius_km": 250,
    "max_stations": 25,
    "max_cloud_layers": 3,
    "default_lat": 40.472,
    "default_lon": -3.561,
    "metar_type_keyword": False,
    "transition_seconds": 0,        # phase-in time FSX uses to reach each new METAR (0 = immediate)
    "freeze_dynamics": True,        # stop FSX evolving the injected weather on its own
    "restore_dynamic_rate": 1,      # dynamic weather rate (0-5) set back when injection is disabled
    "overlay": True,                # always-on-top wind window (needs FSX in windowed mode)
    "overlay_alpha": 0.85,
    "overlay_x": 40,
    "overlay_y": 40,
    "simconnect_dll": "auto",
}


def load_config(base_dir):
    cfg = dict(DEFAULTS)
    path = os.path.join(base_dir, "config.json")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    if cfg["simconnect_dll"] == "auto":
        cfg["simconnect_dll"] = os.path.normpath(os.path.join(base_dir, "..", "SimConnect.dll"))
    return cfg


class App:
    def __init__(self, base_dir, cfg):
        self.base_dir = base_dir
        self.cfg = cfg
        set_lang(cfg.get("language", "en"))
        self.lock = threading.RLock()
        self.logbuf = deque(maxlen=120)
        self.logfile = os.path.join(base_dir, "fsxwl.log")
        self.stations = []
        self.center = (cfg["default_lat"], cfg["default_lon"])
        self.updated = None
        self.last_fetch_pos = None
        self.fetch_error = None   # (key, kwargs), rendered per language
        self.inject = False
        self.inject_note = None
        self.sim = Sim(cfg["simconnect_dll"], self.log)
        self.overlay = Overlay(self)
        self.area_cache = {}      # rounded bbox -> (time, built stations)
        self._stop = threading.Event()
        self._wake = threading.Event()

    # ---------- log ----------
    def log(self, msg):
        line = "%s  %s" % (datetime.now().strftime("%H:%M:%S"), msg)
        with self.lock:
            self.logbuf.append(line)
        try:
            with open(self.logfile, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    # ---------- data ----------
    def _build(self, raw_stations):
        out = []
        for s in raw_stations:
            d = parse_metar(s["raw"])
            s = dict(s)
            s["_d"] = d
            s["sim_metar"] = to_simconnect(
                s["icao"], d, include_type=self.cfg["metar_type_keyword"],
                max_cloud_layers=self.cfg["max_cloud_layers"])
            out.append(s)
        return out

    @staticmethod
    def _public(stations):
        lang = get_lang()
        return [dict({k: v for k, v in s.items() if k != "_d"}, summary=summary(s["_d"], lang),
                     weather=weather_info(s["_d"], lang))
                for s in stations]

    @staticmethod
    def _render(note):
        return t(note[0], **note[1]) if note else ""

    def current_center(self):
        p = self.sim.pos
        if p and time.time() - p["t"] < 30:
            return (p["lat"], p["lon"]), True
        return self.center, False

    def refresh(self):
        (lat, lon), from_sim = self.current_center()
        try:
            raw = net.metars_near(lat, lon, self.cfg["radius_km"], self.cfg["max_stations"])
            stations = self._build(raw)
        except Exception as e:
            with self.lock:
                self.fetch_error = ("fetch_fail", {"err": e})
            self.log(self._render(self.fetch_error))
            return
        with self.lock:
            self.stations = stations
            self.updated = time.time()
            self.fetch_error = None
            self.last_fetch_pos = (lat, lon)
            inject = self.inject
        self.log(t("fetched", n=len(stations), lat=lat, lon=lon))
        if inject:
            self._push()

    def _push(self):
        with self.lock:
            stations = list(self.stations)
        if not (self.sim.connected and stations):
            self.inject_note = ("note_nosend", {})
            return
        secs = int(self.cfg["transition_seconds"])
        self.sim.post(Sim.cmd_apply, stations, secs, bool(self.cfg["freeze_dynamics"]))
        self.inject_note = ("note_sent", {"time": datetime.now().strftime("%H:%M:%S")})
        for delay in (10, 90):
            tm = threading.Timer(delay, self._check, args=("+%ds" % delay,))
            tm.daemon = True
            tm.start()

    def _check(self, label):
        """Logs what FSX really has near the aircraft, to spot the sim overriding the injection."""
        p = self.sim.pos
        if self.inject and self.sim.connected and p:
            self.sim.post(Sim.cmd_check, p["lat"], p["lon"], label)

    def set_inject(self, enabled):
        with self.lock:
            if enabled == self.inject:
                return
            self.inject = enabled
        if enabled:
            if not self.sim.connected:
                self.inject_note = ("note_wait", {})
            self.sim.post(Sim.cmd_enable_custom, bool(self.cfg["freeze_dynamics"]))
            self._push()
            self.log(t("log_inj_on"))
        else:
            self.sim.post(Sim.cmd_restore_global, self._restore_rate())
            self.inject_note = ("note_off", {})
            self.log(t("log_inj_off"))

    def _restore_rate(self):
        return self.cfg["restore_dynamic_rate"] if self.cfg["freeze_dynamics"] else None

    def diag(self):
        pos = self.sim.pos
        if self.inject:
            return t("diag_disable_first")
        if not (self.sim.connected and pos):
            return t("diag_nosim")
        with self.lock:
            stations = list(self.stations)
        if not stations:
            return t("diag_nostations")
        self.sim.post(Sim.cmd_diag, pos["lat"], pos["lon"], stations[0]["_d"], stations[0]["icao"])
        return t("diag_started")

    def _moved_far(self):
        (lat, lon), _ = self.current_center()
        if not self.last_fetch_pos:
            return True
        return net.haversine_km(lat, lon, *self.last_fetch_pos) > self.cfg["radius_km"] * 0.25

    def scheduler(self):
        while not self._stop.is_set():
            due = (self.updated is None
                   or time.time() - self.updated > self.cfg["update_minutes"] * 60
                   or self._moved_far())
            if due or self._wake.is_set():
                self._wake.clear()
                self.refresh()
            self._wake.wait(20)

    def request_refresh(self):
        self._wake.set()

    def state(self):
        p = self.sim.pos
        with self.lock:
            return {
                "lang": get_lang(),
                "sim": {"connected": self.sim.connected, "pos": p, "error": self.sim.last_error},
                "center": {"lat": self.center[0], "lon": self.center[1]},
                "stations": self._public(self.stations),
                "updated": self.updated,
                "fetch_error": self._render(self.fetch_error),
                "inject": {"enabled": self.inject, "note": self._render(self.inject_note)},
                "update_minutes": self.cfg["update_minutes"],
                "overlay": self.overlay.visible,
                "log": list(self.logbuf)[-40:],
            }

    def search(self, q):
        q = q.strip()
        if not q:
            return {"error": t("s_empty")}
        try:
            if len(q) == 4 and q.isalnum():
                found = net.metars_by_ids([q.upper()])
                if found:
                    s = found[0]
                    return {"name": s["icao"], "lat": s["lat"], "lon": s["lon"],
                            "stations": self._public(self._build(found))}
            g = net.geocode(q)
            if not g:
                return {"error": t("s_notfound")}
            lat, lon, name = g
            near = net.metars_near(lat, lon, 150, 8)
            return {"name": name, "lat": lat, "lon": lon, "stations": self._public(self._build(near))}
        except Exception as e:
            return {"error": t("s_error", err=e)}

    AREA_TTL = 300
    AREA_MAX = 150

    def area(self, south, west, north, east, cols=12, rows=8):
        """Stations (with weather) inside the visible map box, thinned to a grid."""
        south, north = max(-90.0, min(south, north)), min(90.0, max(south, north))
        if east - west >= 360:
            west, east = -180.0, 180.0
        else:
            west = (west + 180) % 360 - 180
            east = (east + 180) % 360 - 180
            if east == west:
                west, east = -180.0, 180.0
        cols, rows = max(1, min(int(cols), 30)), max(1, min(int(rows), 20))
        # Round outwards to 0.5 deg so small pans reuse the cache.
        key = (math.floor(south * 2) / 2, math.floor(west * 2) / 2, math.ceil(north * 2) / 2, math.ceil(east * 2) / 2)
        now = time.time()
        with self.lock:
            hit = self.area_cache.get(key)
        if hit and now - hit[0] < self.AREA_TTL:
            built = hit[1]
        else:
            try:
                built = self._build(net.metars_in_bbox(*key))
            except Exception as e:
                return {"error": t("fetch_fail", err=e), "stations": []}
            with self.lock:
                self.area_cache = {k: v for k, v in self.area_cache.items() if now - v[0] < self.AREA_TTL}
                if len(self.area_cache) > 40:
                    self.area_cache.clear()
                self.area_cache[key] = (now, built)
        inside = [s for s in built
                  if south <= s["lat"] <= north
                  and (west <= s["lon"] <= east if west <= east else (s["lon"] >= west or s["lon"] <= east))]
        shown = net.thin_grid(inside, south, west, north, east, cols, rows)[:self.AREA_MAX]
        return {"total": len(inside), "stations": self._public(shown)}

    def run(self):
        self.log(t("start"))
        self.sim.start()
        self.overlay.start()
        threading.Thread(target=self.scheduler, daemon=True).start()
        handler = make_handler(self)
        srv = ThreadingHTTPServer(("127.0.0.1", self.cfg["port"]), handler)
        self.log(t("ui_at", port=self.cfg["port"]))
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if self.inject and self.sim.connected:
                self.sim.post(Sim.cmd_restore_global, self._restore_rate())
                time.sleep(1.0)
            self._stop.set()
            self.sim.stop()
            srv.server_close()


def make_handler(app):
    port = app.cfg["port"]
    allowed = {"http://localhost:%d" % port, "http://127.0.0.1:%d" % port}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/api/state":
                return self._json(app.state())
            if u.path == "/api/area":
                qs = parse_qs(u.query)
                try:
                    box = [float(qs[k][0]) for k in ("s", "w", "n", "e")]
                    grid = [int(qs.get(k, [d])[0]) for k, d in (("cols", 12), ("rows", 8))]
                except (KeyError, ValueError):
                    return self._json({"error": "bbox"}, 400)
                if not all(map(math.isfinite, box)):
                    return self._json({"error": "bbox"}, 400)
                return self._json(app.area(*box, *grid))
            if u.path == "/api/search":
                q = parse_qs(u.query).get("q", [""])[0]
                return self._json(app.search(q))
            if u.path in ("/", "/index.html"):
                with open(os.path.join(WEB, "index.html"), "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self):
            # Defence: only accept requests from our own page (another website cannot press the buttons).
            origin = self.headers.get("Origin")
            if self.headers.get("X-FSXWL") != "1" or (origin and origin not in allowed):
                return self._json({"error": "forbidden"}, 403)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json({"error": "json"}, 400)
            if self.path == "/api/inject":
                app.set_inject(bool(data.get("enabled")))
                return self._json({"ok": True})
            if self.path == "/api/overlay":
                app.overlay.set_visible(bool(data.get("enabled")))
                return self._json({"ok": True})
            if self.path == "/api/diag":
                return self._json({"ok": True, "msg": app.diag()})
            if self.path == "/api/refresh":
                app.request_refresh()
                return self._json({"ok": True})
            if self.path == "/api/lang":
                lang = data.get("lang")
                if lang not in SUPPORTED:
                    return self._json({"error": "lang"}, 400)
                set_lang(lang)
                return self._json({"ok": True, "lang": lang})
            self.send_error(404)

    return H

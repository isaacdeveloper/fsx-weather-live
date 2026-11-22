"""Connection to FSX through SimConnect.dll (ctypes, __stdcall, 32-bit).

All SimConnect calls are made on a single thread (the worker thread);
the rest of the app only queues commands with `post()`.
"""
import ctypes
import os
import queue
import struct
import sys
import threading
import time

from .i18n import t

EXC_NAMES = [
    "NONE", "ERROR", "SIZE_MISMATCH", "UNRECOGNIZED_ID", "UNOPENED", "VERSION_MISMATCH",
    "TOO_MANY_GROUPS", "NAME_UNRECOGNIZED", "TOO_MANY_EVENT_NAMES", "EVENT_ID_DUPLICATE",
    "TOO_MANY_MAPS", "TOO_MANY_OBJECTS", "TOO_MANY_REQUESTS", "WEATHER_INVALID_PORT",
    "WEATHER_INVALID_METAR", "WEATHER_UNABLE_TO_GET_OBSERVATION",
    "WEATHER_UNABLE_TO_CREATE_STATION", "WEATHER_UNABLE_TO_REMOVE_STATION",
    "INVALID_DATA_TYPE", "INVALID_DATA_SIZE", "DATA_ERROR", "INVALID_ARRAY",
    "CREATE_OBJECT_FAILED", "LOAD_FLIGHTPLAN_FAILED", "OPERATION_INVALID_FOR_OBJECT_TYPE",
    "ILLEGAL_OPERATION", "ALREADY_SUBSCRIBED", "INVALID_ENUM", "DEFINITION_ERROR",
    "DUPLICATE_ID", "DATUM_ID", "OUT_OF_BOUNDS", "ALREADY_CREATED",
    "OBJECT_OUTSIDE_REALITY_BUBBLE", "OBJECT_CONTAINER", "OBJECT_AI", "OBJECT_ATC",
    "OBJECT_SCHEDULE",
]

# SIMCONNECT_RECV_ID (SimConnect.h)
RECV_EXCEPTION, RECV_OPEN, RECV_QUIT, RECV_SIMOBJECT_DATA, RECV_WEATHER_OBS = 1, 2, 3, 8, 10
DATATYPE_FLOAT64 = 4
PERIOD_SECOND = 4
OBJECT_ID_USER = 0
UNUSED = 0xFFFFFFFF

DEF_POS, REQ_POS = 1, 1
REQ_WX_BASE = 1000


def is_32bit_python():
    return struct.calcsize("P") * 8 == 32


class Sim:
    def __init__(self, dll_path, log):
        self.dll_path = dll_path
        self.log = log
        self.connected = False
        self.pos = None            # dict lat, lon, alt_ft, hdg, gs_kt, t
        self.readback = {}         # icao -> METAR returned by FSX
        self.last_error = ""
        self._h = None
        self._dll = None
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._created = set()
        self._custom_on = False
        self._diag_running = False
        self._exc = []             # exceptions received (for the diagnostic)
        self._req = REQ_WX_BASE
        self._thread = threading.Thread(target=self._run, name="simconnect", daemon=True)

    # ---------- public API (any thread) ----------
    def start(self):
        if sys.platform != "win32":
            self.last_error = t("sim_win")
            return
        if not is_32bit_python():
            self.last_error = t("sim_32")
            self.log(self.last_error)
            return
        if not os.path.isfile(self.dll_path):
            self.last_error = t("sim_nodll", path=self.dll_path)
            self.log(self.last_error)
            return
        self._thread.start()

    def stop(self):
        self._stop.set()

    def post(self, fn, *args):
        self._q.put((fn, args))

    # ---------- SimConnect calls (worker thread only) ----------
    def _bind(self):
        d = ctypes.WinDLL(self.dll_path)
        H, C = ctypes.c_void_p, ctypes.c_char_p
        L, U, F, I = ctypes.c_long, ctypes.c_uint32, ctypes.c_float, ctypes.c_int

        def sig(name, args):
            f = getattr(d, name)
            f.restype = L
            f.argtypes = args
            return f

        self._Open = sig("SimConnect_Open", [ctypes.POINTER(H), C, H, U, H, U])
        self._Close = sig("SimConnect_Close", [H])
        self._AddDef = sig("SimConnect_AddToDataDefinition", [H, U, C, C, I, F, U])
        self._ReqData = sig("SimConnect_RequestDataOnSimObject", [H, U, U, U, I, U, U, U, U])
        self._Next = sig("SimConnect_GetNextDispatch",
                         [H, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(U)])
        self._SetCustom = sig("SimConnect_WeatherSetModeCustom", [H])
        self._SetGlobal = sig("SimConnect_WeatherSetModeGlobal", [H])
        self._Create = sig("SimConnect_WeatherCreateStation", [H, U, C, C, F, F, F])
        self._Remove = sig("SimConnect_WeatherRemoveStation", [H, U, C])
        self._SetObs = sig("SimConnect_WeatherSetObservation", [H, U, C])
        self._ReqNearest = sig("SimConnect_WeatherRequestObservationAtNearestStation", [H, U, F, F])
        self._ReqStation = sig("SimConnect_WeatherRequestObservationAtStation", [H, U, C])
        self._dll = d

    def _connect(self):
        h = ctypes.c_void_p()
        hr = self._Open(ctypes.byref(h), b"FSX Weather Live", None, 0, None, 0)
        if hr != 0:
            return False
        self._h = h
        names = [(b"Plane Latitude", b"degrees"), (b"Plane Longitude", b"degrees"),
                 (b"Plane Altitude", b"feet"), (b"Plane Heading Degrees True", b"degrees"),
                 (b"Ground Velocity", b"knots")]
        for n, u in names:
            self._AddDef(h, DEF_POS, n, u, DATATYPE_FLOAT64, 0.0, UNUSED)
        self._ReqData(h, REQ_POS, DEF_POS, OBJECT_ID_USER, PERIOD_SECOND, 0, 0, 0, 0)
        self.connected = True
        self._created.clear()
        self._custom_on = False
        self.log(t("sim_connected"))
        return True

    def _disconnect(self):
        if self._h is not None:
            try:
                self._Close(self._h)
            except Exception:
                pass
        self._h = None
        self.connected = False
        self.pos = None
        self._created.clear()
        self._custom_on = False

    def _dispatch(self):
        for _ in range(200):
            ptr = ctypes.c_void_p()
            cb = ctypes.c_uint32()
            hr = self._Next(self._h, ctypes.byref(ptr), ctypes.byref(cb))
            if hr != 0 or not ptr.value:
                return True
            data = ctypes.string_at(ptr.value, cb.value)
            _size, _ver, rid = struct.unpack_from("<III", data, 0)
            if rid == RECV_QUIT:
                self.log(t("sim_quit"))
                return False
            if rid == RECV_EXCEPTION:
                exc, sendid, idx = struct.unpack_from("<III", data, 12)
                name = EXC_NAMES[exc] if exc < len(EXC_NAMES) else str(exc)
                self.last_error = t("sim_exc", name=name, pid=sendid, idx=idx)
                self._exc.append(name)
                if not self._diag_running:
                    self.log(self.last_error)
            elif rid == RECV_SIMOBJECT_DATA and cb.value >= 40 + 5 * 8:
                req = struct.unpack_from("<I", data, 12)[0]
                if req == REQ_POS:
                    lat, lon, alt, hdg, gs = struct.unpack_from("<5d", data, 40)
                    self.pos = {"lat": lat, "lon": lon, "alt_ft": alt, "hdg": hdg,
                                "gs_kt": gs, "t": time.time()}
            elif rid == RECV_WEATHER_OBS:
                req = struct.unpack_from("<I", data, 12)[0]
                txt = data[16:].split(b"\0", 1)[0].decode("ascii", "replace")
                self.readback[req] = txt
                if req >= 5000:
                    self.log(t("sim_readback", req=req, txt=txt))
        return True

    def _run(self):
        try:
            self._bind()
        except Exception as e:  # DLL cannot be loaded
            self.last_error = t("sim_loadfail", err=e)
            self.log(self.last_error)
            return
        while not self._stop.is_set():
            if not self.connected:
                if not self._connect():
                    time.sleep(3)
                    continue
            try:
                while True:
                    fn, args = self._q.get_nowait()
                    try:
                        fn(self, *args)
                    except Exception as e:
                        self.log(t("sim_cmd_err", err=repr(e)))
            except queue.Empty:
                pass
            try:
                if not self._dispatch():
                    self._disconnect()
            except Exception as e:
                self.log(t("sim_read_err", err=repr(e)))
                self._disconnect()
            time.sleep(0.1)
        self._disconnect()

    # ---------- weather commands (run on the worker thread) ----------
    def _next_req(self):
        self._req += 1
        return self._req

    def cmd_enable_custom(self):
        hr = self._SetCustom(self._h)
        self._custom_on = True
        self.log("WeatherSetModeCustom hr=0x%08X" % (hr & 0xFFFFFFFF))

    def cmd_restore_global(self):
        if not self._custom_on and not self._created:
            return  # FSX weather was never touched on this connection: nothing to restore
        for icao in list(self._created):
            self._Remove(self._h, self._next_req(), icao.encode("ascii"))
        self._created.clear()
        self._custom_on = False
        hr = self._SetGlobal(self._h)
        self.log(t("sim_restore", hr=hr & 0xFFFFFFFF))

    def cmd_apply(self, stations, seconds):
        """stations: list of dicts with icao, name, lat, lon, elev_m, sim_metar."""
        from collections import Counter
        if not self._custom_on:
            self.cmd_enable_custom()
        self._exc.clear()
        self._diag_running = True      # silences per-exception logging
        ok = 0
        try:
            for s in stations:
                icao = s["icao"].encode("ascii", "ignore")
                if s["icao"] not in self._created:
                    hr = self._Create(self._h, self._next_req(), icao, s.get("name", "").encode("ascii", "ignore"),
                                      float(s["lat"]), float(s["lon"]), float(s.get("elev_m") or 0.0))
                    self._created.add(s["icao"])
                    if hr != 0:
                        self.log("CreateStation %s hr=0x%08X" % (s["icao"], hr & 0xFFFFFFFF))
                hr = self._SetObs(self._h, int(seconds), s["sim_metar"].encode("ascii", "ignore"))
                if hr == 0:
                    ok += 1
                else:
                    self.log("SetObservation %s hr=0x%08X" % (s["icao"], hr & 0xFFFFFFFF))
            self._pump(0.6)
        finally:
            self._diag_running = False
        c = Counter(self._exc)
        extra = t("sim_exc_list", lst=", ".join("%s x%d" % kv for kv in sorted(c.items()))) if c \
            else t("sim_noexc")
        self.log(t("sim_sent", ok=ok, n=len(stations), extra=extra))

    # ---------- diagnostic ----------
    def _pump(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self._dispatch()
            time.sleep(0.05)

    def _diag_set(self, label, metar):
        self._exc.clear()
        hr = self._SetObs(self._h, 600, metar.encode("ascii", "ignore"))
        self._pump(0.8)
        res = list(self._exc)
        self.log("DIAG %-22s -> %s   [%s]" % (label, t("dg_ok") if not res and hr == 0
                                               else t("dg_bad") + " " + ",".join(res or ["hr=0x%08X" % (hr & 0xFFFFFFFF)]),
                                               metar))

    def cmd_diag(self, lat, lon, parsed, sample_icao):
        """Asks FSX for its own format and tries string variants, logging which ones it accepts."""
        import re
        from .metar import to_simconnect
        self._diag_running = True
        try:
            self.log(t("dg_start"))
            self._ReqNearest(self._h, 5001, float(lat), float(lon))
            self._pump(1.5)
            near = self.readback.get(5001, "")
            self._ReqStation(self._h, 5002, b"GLOB")
            self._pump(1.5)
            sid = re.split(r"[&\s]", near.strip())[0] if near.strip() else ""
            if not re.fullmatch(r"[A-Z0-9]{3,4}", sid or ""):
                sid = sample_icao
            if not near:
                self.log(t("dg_nonear"))
            self.log(t("dg_station", sid=sid))

            base = to_simconnect(sid, parsed, include_type=False)
            with_type = to_simconnect(sid, parsed, include_type=True)
            stamp = base.split()[1]
            self.cmd_enable_custom()
            for label, m in [
                (t("dg_t1"), with_type),
                (t("dg_t2"), base),
                (t("dg_t3"), re.sub(r"\b\d+KM\b", "6SM", base)),
                (t("dg_t4"), "%s %s 27012KT SKC 14/05 Q1021" % (sid, stamp)),
                (t("dg_t5"), "%s 030405Z 27007KT 15SM SKC 17/13 A2992" % sid),
            ]:
                self._diag_set(label, m)

            self._SetGlobal(self._h)
            self._custom_on = False
            for label, m in [
                (t("dg_g1"), re.sub(r"^\S+", "GLOB", base, count=1)),
                (t("dg_g2"), re.sub(r"^\S+", "GLOB", with_type, count=1)),
                (t("dg_g3"), "GLOB 030405Z 27007KT 15SM SKC 17/13 A2992"),
            ]:
                self._diag_set(label, m)
            self.log(t("dg_end"))
        finally:
            self._diag_running = False

"""Decodes a standard METAR and builds the SimConnect (FSX) METAR string.

The SimConnect format (SimConnect_WeatherSetObservation) is NOT standard
METAR: it uses sections in a fixed order and its own syntax. Only the subset
documented by Microsoft is emitted here:

  ICAO [METAR] DDHHMMZ  DDDSSKT[GXX]  [DDDVDDD]  VIS  [WEATHER]  CLOUDS  TT/DD  Qhhhh

If a value is missing, its section is omitted instead of being made up.
"""
import re
from datetime import datetime, timezone
from fractions import Fraction

_KT_PER_UNIT = {"KT": 1.0, "MPS": 1.943844, "KMH": 0.539957}
_SM_M = 1609.344

_WIND = re.compile(r"^(VRB|\d{3})(\d{2,3})(?:G(\d{2,3}))?(KT|MPS|KMH)$")
_WINDVAR = re.compile(r"^(\d{3})V(\d{3})$")
_VIS_SM = re.compile(r"^(P|M)?(\d+)(?:/(\d+))?SM$")
_CLOUD = re.compile(r"^(FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?$")
_VV = re.compile(r"^VV(\d{3})$")
_TEMP = re.compile(r"^(M?\d{1,2})/(M?\d{1,2})?$")
_QNH = re.compile(r"^Q(\d{4})$")
_ALT = re.compile(r"^A(\d{4})$")
_TIME = re.compile(r"^\d{6}Z$")

# Weather phenomena accepted by SimConnect (BC -> not emitted; PL -> PE).
_WX_DESC = "MI|PR|BC|DR|BL|SH|TS|FZ"
_WX_PHEN = "DZ|RA|SN|SG|IC|PL|PE|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS"
_WX = re.compile(r"^(\+|-|VC)?((?:%s))?((?:%s)*)$" % (_WX_DESC, _WX_PHEN))
_WX_OUT = re.compile(r"^(\+|-|VC)?(MI|PR|DR|BL|SH|TS|FZ)?((?:%s)*)$" % _WX_PHEN.replace("PL|", ""))

_STOP = {"RMK", "TEMPO", "BECMG", "FM", "PROB30", "PROB40"}
_SKIP = {"AUTO", "COR", "NIL", "NOSIG", "METAR", "SPECI", "NSW", "RE"}


def _signed(s):
    return -int(s[1:]) if s.startswith("M") else int(s)


def parse_metar(raw):
    """Returns a dict with the decoded fields (those present)."""
    d = {
        "raw": raw, "icao": None, "wind": None, "wind_var": None, "vis_m": None,
        "wx": [], "clouds": [], "temp": None, "dew": None, "qnh_hpa": None,
        "cavok": False,
    }
    toks = raw.replace("=", " ").split()
    while toks and toks[0] in ("METAR", "SPECI"):
        toks.pop(0)
    if toks and re.fullmatch(r"[A-Z0-9]{3,4}", toks[0]) and not _TIME.match(toks[0]):
        d["icao"] = toks.pop(0)

    pending_int = None
    for t in toks:
        if t in _STOP:
            break
        if t in _SKIP or _TIME.match(t):
            continue
        if t == "CAVOK":
            d["cavok"] = True
            d["vis_m"] = 10000
            continue
        m = _WIND.match(t)
        if m and d["wind"] is None:
            unit = m.group(4)
            k = _KT_PER_UNIT[unit]
            d["wind"] = {
                "dir": None if m.group(1) == "VRB" else int(m.group(1)),
                "kt": int(round(int(m.group(2)) * k)),
                "gust_kt": int(round(int(m.group(3)) * k)) if m.group(3) else None,
            }
            continue
        m = _WINDVAR.match(t)
        if m and d["wind"] is not None:
            d["wind_var"] = (int(m.group(1)), int(m.group(2)))
            continue
        if t.startswith("R") and "/" in t and t[1:3].isdigit():
            continue  # RVR
        if d["vis_m"] is None:
            if re.fullmatch(r"\d{4}", t) and d["wind"] is not None:
                d["vis_m"] = 10000 if t == "9999" else int(t)
                continue
            if re.fullmatch(r"\d{1,2}", t):
                pending_int = int(t)
                continue
            m = _VIS_SM.match(t)
            if m:
                num = int(m.group(2))
                sm = num / int(m.group(3)) if m.group(3) else float(num)
                if pending_int:
                    sm += pending_int
                if m.group(1) == "P":
                    sm = max(sm, 6.1)
                d["vis_m"] = int(sm * _SM_M)
                continue
        m = _CLOUD.match(t)
        if m:
            d["clouds"].append({"cover": m.group(1), "base_ft": int(m.group(2)) * 100,
                                "type": m.group(3)})
            continue
        m = _VV.match(t)
        if m:
            d["clouds"].append({"cover": "OVC", "base_ft": int(m.group(1)) * 100, "type": None})
            continue
        if t in ("SKC", "CLR", "NSC", "NCD"):
            continue
        m = _TEMP.match(t)
        if m and d["temp"] is None:
            d["temp"] = _signed(m.group(1))
            d["dew"] = _signed(m.group(2)) if m.group(2) else None
            continue
        m = _QNH.match(t)
        if m:
            d["qnh_hpa"] = int(m.group(1))
            continue
        m = _ALT.match(t)
        if m:
            d["qnh_hpa"] = int(round(int(m.group(1)) / 100.0 * 33.8639))
            continue
        if len(t) >= 2 and _WX.match(t) and t not in ("VC",) and re.search(_WX_DESC + "|" + _WX_PHEN, t):
            d["wx"].append(t)
            continue
    d["clouds"].sort(key=lambda c: c["base_ft"])
    return d


def _vis_token(vis_m):
    if vis_m is None:
        return None
    if vis_m >= 9999:
        km = max(10, min(100, int(round(vis_m / 1000.0))))
        return "%dKM" % km
    sm = vis_m / _SM_M
    if sm >= 1:
        return "%dSM" % max(1, int(sm + 0.5 + 1e-3))
    eighths = int(round(sm * 8))
    if eighths < 2:
        return "M1/4SM"
    f = Fraction(eighths, 8)
    return "1SM" if f == 1 else "%d/%dSM" % (f.numerator, f.denominator)


def _wx_token(t):
    t = t.replace("PL", "PE")
    if "BC" in t:
        return None
    return t if _WX_OUT.match(t) and len(t) >= 2 else None


def _temp_token(v):
    return ("-" if v < 0 else "") + "%02d" % abs(v)


def to_simconnect(icao, d, now=None, include_type=True, max_cloud_layers=3):
    """Builds the METAR string in SimConnect format."""
    now = now or datetime.now(timezone.utc)
    parts = [icao]
    if include_type:
        parts.append("METAR")
    parts.append(now.strftime("%d%H%MZ"))

    w = d.get("wind")
    if w:
        # North is 360 in a METAR; 000 only goes with a calm (00000KT).
        dd = "VRB" if w["dir"] is None else "%03d" % ((w["dir"] % 360) or (360 if w["kt"] else 0))
        s = "%s%02d" % (dd, min(w["kt"], 400))
        if w.get("gust_kt"):
            s += "G%02d" % min(w["gust_kt"], 400)
        parts.append(s + "KT")
        if d.get("wind_var"):
            parts.append("%03dV%03d" % d["wind_var"])
    else:
        parts.append("00000KT")

    v = _vis_token(d.get("vis_m"))
    if v:
        parts.append(v)

    for t in d.get("wx", []):
        tok = _wx_token(t)
        if tok:
            parts.append(tok)

    layers = d.get("clouds", [])[:max_cloud_layers]
    if layers:
        for c in layers:
            parts.append("%s%03d%s" % (c["cover"], min(999, c["base_ft"] // 100),
                                       "CB" if c.get("type") == "CB" else ""))
    else:
        parts.append("SKC")

    if d.get("temp") is not None:
        dew = d["dew"] if d.get("dew") is not None else d["temp"]
        parts.append("%s/%s" % (_temp_token(d["temp"]), _temp_token(dew)))
    if d.get("qnh_hpa"):
        parts.append("Q%d" % d["qnh_hpa"])
    return " ".join(parts)


_SUM = {
    "es": {"wind": "Viento {b} a {kt} kt", "var": "variable", "gust": " (rachas {g})",
           "vis": "Vis. {x:.1f} km", "vis10": "Vis. ≥10 km", "wx": "Fenómenos: ", "cl": "Nubes: ",
           "clear": "Cielo despejado"},
    "en": {"wind": "Wind {b} at {kt} kt", "var": "variable", "gust": " (gusts {g})",
           "vis": "Vis. {x:.1f} km", "vis10": "Vis. ≥10 km", "wx": "Weather: ", "cl": "Clouds: ",
           "clear": "Clear sky"},
}


def summary(d, lang="es"):
    """Human-readable summary (es/en) for the UI."""
    L = _SUM.get(lang, _SUM["es"])
    out = []
    w = d.get("wind")
    if w:
        base = L["var"] if w["dir"] is None else "%d°" % w["dir"]
        txt = L["wind"].format(b=base, kt=w["kt"])
        if w.get("gust_kt"):
            txt += L["gust"].format(g=w["gust_kt"])
        out.append(txt)
    if d.get("vis_m") is not None:
        out.append(L["vis"].format(x=d["vis_m"] / 1000.0) if d["vis_m"] < 9999 else L["vis10"])
    if d.get("wx"):
        out.append(L["wx"] + " ".join(d["wx"]))
    if d.get("clouds"):
        out.append(L["cl"] + " ".join("%s %d ft%s" % (c["cover"], c["base_ft"],
                                                      " CB" if c.get("type") == "CB" else "")
                                      for c in d["clouds"]))
    elif d.get("cavok") or d.get("vis_m"):
        out.append(L["clear"])
    if d.get("temp") is not None:
        out.append("%d/%d °C" % (d["temp"], d["dew"] if d["dew"] is not None else d["temp"]))
    if d.get("qnh_hpa"):
        out.append("QNH %d" % d["qnh_hpa"])
    return " · ".join(out)


def summary_es(d):
    return summary(d, "es")


_COND_TXT = {
    "es": {"clear": "Despejado", "few": "Poco nuboso", "partly": "Parcialmente nuboso",
           "cloudy": "Muy nuboso", "overcast": "Cubierto", "mist": "Neblina", "fog": "Niebla",
           "haze": "Calima", "drizzle": "Llovizna", "rain": "Lluvia", "showers": "Chubascos",
           "snow": "Nieve", "hail": "Granizo", "thunder": "Tormenta", "unknown": "Sin datos"},
    "en": {"clear": "Clear", "few": "Mostly clear", "partly": "Partly cloudy",
           "cloudy": "Mostly cloudy", "overcast": "Overcast", "mist": "Mist", "fog": "Fog",
           "haze": "Haze", "drizzle": "Drizzle", "rain": "Rain", "showers": "Showers",
           "snow": "Snow", "hail": "Hail", "thunder": "Thunderstorm", "unknown": "No data"},
}
_COVER_RANK = {"FEW": 1, "SCT": 2, "BKN": 3, "OVC": 4}


def condition(d):
    """Weather category used to pick the map icon (phenomena take precedence over clouds)."""
    wx = " ".join(t for t in d.get("wx", []) if not t.startswith("VC"))
    if "TS" in wx:
        return "thunder"
    if "GR" in wx or "GS" in wx:
        return "hail"
    if any(p in wx for p in ("SN", "SG", "PL", "PE", "IC")):
        return "snow"
    if "SH" in wx:
        return "showers"
    if "RA" in wx:
        return "rain"
    if "DZ" in wx:
        return "drizzle"
    if "FG" in wx:
        return "fog"
    if "BR" in wx:
        return "mist"
    if any(p in wx for p in ("HZ", "FU", "DU", "SA", "VA")):
        return "haze"
    clouds = d.get("clouds") or []
    if clouds:
        top = max(_COVER_RANK.get(c["cover"], 0) for c in clouds)
        return {1: "few", 2: "partly", 3: "cloudy", 4: "overcast"}.get(top, "clear")
    if d.get("cavok") or d.get("vis_m") is not None or d.get("wind"):
        return "clear"
    return "unknown"


def weather_info(d, lang="es"):
    """Compact data for the map icons and panel."""
    c = condition(d)
    return {"cond": c, "text": _COND_TXT.get(lang, _COND_TXT["es"])[c],
            "wind": d.get("wind"), "vis_m": d.get("vis_m"), "temp": d.get("temp"),
            "dew": d.get("dew"), "qnh_hpa": d.get("qnh_hpa")}

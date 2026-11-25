"""User-defined weather: converts the editor's form into the decoded-METAR dict
that `metar.to_simconnect` understands, and back (to load a real station into the editor).

Form (all keys optional, values are clamped to sane ranges):
  wind:   {dir: 0-360 | null (variable), kt, gust_kt, var: +/- degrees of variation}
  vis_m:  visibility in metres (>= 9999 = 10 km or more)
  wx:     {intensity: "-" | "" | "+", type: one of WX_TYPES}
  clouds: [{cover: FEW|SCT|BKN|OVC, base_ft, cb: bool}, ...]  (up to 3)
  temp, dew (deg C), qnh (hPa)
"""

# Weather types offered by the editor: SimConnect code -> takes an intensity prefix?
WX_TYPES = {
    "": False,
    "RA": True, "SHRA": True, "DZ": True, "FZRA": True, "FZDZ": True,
    "SN": True, "SHSN": True, "PE": True, "TSRA": True, "TSSN": True, "TSGR": True, "TS": False,
    "BR": False, "FG": False, "FZFG": False, "HZ": False, "SA": False, "DU": False,
}
COVERS = ("FEW", "SCT", "BKN", "OVC")
MAX_LAYERS = 3


def _num(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return max(lo, min(hi, v))


def form_to_dict(form):
    form = form or {}
    w = form.get("wind") or {}
    kt = int(round(_num(w.get("kt"), 0, 150, 0)))
    gust = int(round(_num(w.get("gust_kt"), 0, 200, 0)))
    wdir = w.get("dir")
    wdir = None if wdir is None or wdir == "VRB" else int(round(_num(wdir, 0, 360, 0))) % 360
    if wdir == 0 and kt > 0:
        wdir = 360
    wind = {"dir": wdir, "kt": kt, "gust_kt": gust if gust > kt else None}
    var = int(round(_num(w.get("var"), 0, 180, 0)))
    wind_var = None
    if wdir is not None and kt > 0 and var >= 10:
        lo, hi = (wdir - var) % 360, (wdir + var) % 360
        wind_var = (lo or 360, hi or 360)

    wx = form.get("wx") or {}
    typ = str(wx.get("type") or "").upper()
    wx_list = []
    if typ in WX_TYPES and typ:
        inten = wx.get("intensity") if WX_TYPES[typ] else ""
        wx_list.append((inten if inten in ("-", "+") else "") + typ)

    clouds = []
    for c in (form.get("clouds") or [])[:MAX_LAYERS]:
        cover = str((c or {}).get("cover") or "").upper()
        if cover not in COVERS:
            continue
        base = int(round(_num(c.get("base_ft"), 0, 40000, 3000) / 100.0)) * 100
        clouds.append({"cover": cover, "base_ft": base, "type": "CB" if c.get("cb") else None})
    clouds.sort(key=lambda c: c["base_ft"])

    temp = int(round(_num(form.get("temp"), -60, 55, 15)))
    dew = int(round(_num(form.get("dew"), -70, 55, temp - 5)))
    return {
        "raw": "", "icao": None, "wind": wind, "wind_var": wind_var,
        "vis_m": int(round(_num(form.get("vis_m"), 0, 100000, 10000))),
        "wx": wx_list, "clouds": clouds, "temp": temp, "dew": min(dew, temp),
        "qnh_hpa": int(round(_num(form.get("qnh"), 900, 1080, 1013))), "cavok": False,
    }


def dict_to_form(d):
    """Decoded METAR (metar.parse_metar) -> editor form, to start from real weather."""
    w = d.get("wind") or {"dir": 0, "kt": 0, "gust_kt": None}
    var = 0
    if d.get("wind_var") and w.get("dir") is not None:
        lo, hi = d["wind_var"]
        var = ((hi - lo) % 360) // 2
    wx = {"intensity": "", "type": ""}
    for tok in d.get("wx", []):
        inten = tok[0] if tok[0] in "+-" else ""
        core = tok.lstrip("+-").replace("PL", "PE")
        if core in WX_TYPES and core:
            wx = {"intensity": inten, "type": core}
            break
    return {
        "wind": {"dir": w.get("dir"), "kt": w.get("kt") or 0, "gust_kt": w.get("gust_kt") or 0, "var": var},
        "vis_m": d.get("vis_m") if d.get("vis_m") is not None else 10000,
        "wx": wx,
        "clouds": [{"cover": c["cover"], "base_ft": c["base_ft"], "cb": c.get("type") == "CB"}
                   for c in d.get("clouds", [])[:MAX_LAYERS]],
        "temp": d["temp"] if d.get("temp") is not None else 15,
        "dew": d["dew"] if d.get("dew") is not None else (d.get("temp") or 15) - 5,
        "qnh": d.get("qnh_hpa") or 1013,
    }

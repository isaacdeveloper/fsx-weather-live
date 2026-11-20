"""Descargas: METAR de NOAA (sin clave) y geocodificación con Nominatim."""
import json
import math
import urllib.parse
import urllib.request

UA = "FSXWeatherLive/0.1 (herramienta personal para simulador de vuelo)"
NOAA = "https://aviationweather.gov/api/data/metar"
NOMINATIM = "https://nominatim.openstreetmap.org/search"


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace").strip()
    if not body:
        return []
    return json.loads(body)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _clean(items):
    """Se queda con lo imprescindible; tolera campos ausentes."""
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        icao = it.get("icaoId") or it.get("station_id")
        raw = it.get("rawOb") or it.get("raw_text")
        lat, lon = it.get("lat"), it.get("lon")
        if not (icao and raw and isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
            continue
        out.append({"icao": str(icao), "raw": str(raw), "lat": float(lat), "lon": float(lon),
                    "elev_m": it.get("elev") if isinstance(it.get("elev"), (int, float)) else None,
                    "name": it.get("name") or ""})
    return out


def metars_near(lat, lon, radius_km=250, limit=25):
    """METAR más recientes dentro de un cuadro alrededor de (lat, lon)."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    bbox = "%.3f,%.3f,%.3f,%.3f" % (lat - dlat, lon - dlon, lat + dlat, lon + dlon)
    url = NOAA + "?" + urllib.parse.urlencode({"bbox": bbox, "format": "json"})
    items = _clean(_get_json(url))
    seen, res = set(), []
    for s in items:
        if s["icao"] in seen:
            continue
        seen.add(s["icao"])
        s["dist_km"] = haversine_km(lat, lon, s["lat"], s["lon"])
        if s["dist_km"] <= radius_km:
            res.append(s)
    res.sort(key=lambda s: s["dist_km"])
    return res[:limit]


def metars_by_ids(ids):
    url = NOAA + "?" + urllib.parse.urlencode({"ids": ",".join(ids), "format": "json"})
    return _clean(_get_json(url))


def geocode(query):
    """Dirección -> (lat, lon, nombre) con OpenStreetMap Nominatim (uso puntual)."""
    url = NOMINATIM + "?" + urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    res = _get_json(url)
    if not res:
        return None
    r = res[0]
    return float(r["lat"]), float(r["lon"]), r.get("display_name", query)

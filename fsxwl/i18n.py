"""Backend strings in Spanish (es) and English (en).

The language is global (a single person uses the app): it is set with `set_lang()`
at startup (config.json -> "language") and from the UI toggle.
"""

SUPPORTED = ("es", "en")
_lang = "en"

STR = {
    # --- app ---
    "start": {"es": "Arrancando FSX Weather Live", "en": "Starting FSX Weather Live"},
    "ui_at": {"es": "Interfaz en http://localhost:{port}", "en": "Interface at http://localhost:{port}"},
    "fetch_fail": {"es": "No se pudo descargar el tiempo: {err}", "en": "Could not download weather: {err}"},
    "fetched": {"es": "METAR descargados: {n} estaciones cerca de {lat:.2f}, {lon:.2f}",
                "en": "METARs downloaded: {n} stations near {lat:.2f}, {lon:.2f}"},
    "note_nosend": {"es": "FSX no conectado: no se envía nada", "en": "FSX not connected: nothing sent"},
    "note_sent": {"es": "Enviado a FSX a las {time}", "en": "Sent to FSX at {time}"},
    "note_wait": {"es": "FSX no conectado (se aplicará cuando conecte)",
                  "en": "FSX not connected (will apply once it connects)"},
    "note_off": {"es": "Desactivada: FSX recupera su tiempo", "en": "Disabled: FSX gets its own weather back"},
    "log_inj_on": {"es": "Inyección ACTIVADA", "en": "Injection ENABLED"},
    "log_inj_off": {"es": "Inyección DESACTIVADA", "en": "Injection DISABLED"},
    "diag_disable_first": {"es": "Desactiva primero la inyección y vuelve a pulsar el diagnóstico",
                           "en": "Disable injection first, then run the diagnostic again"},
    "diag_nosim": {"es": "FSX no está conectado", "en": "FSX is not connected"},
    "diag_nostations": {"es": "Aún no hay estaciones descargadas", "en": "No stations downloaded yet"},
    "diag_started": {"es": "Diagnóstico lanzado: mira el Registro en unos segundos",
                     "en": "Diagnostic started: check the Log in a few seconds"},
    "s_empty": {"es": "Escribe una dirección o un código ICAO", "en": "Enter an address or an ICAO code"},
    "s_notfound": {"es": "No encuentro ese lugar", "en": "Place not found"},
    "s_error": {"es": "Error en la búsqueda: {err}", "en": "Search error: {err}"},
    # --- sim ---
    "sim_win": {"es": "SimConnect solo existe en Windows", "en": "SimConnect only exists on Windows"},
    "sim_32": {"es": "Hace falta Python de 32 bits (SimConnect.dll de FSX es de 32 bits)",
               "en": "32-bit Python is required (FSX's SimConnect.dll is 32-bit)"},
    "sim_nodll": {"es": "No encuentro SimConnect.dll en {path}", "en": "SimConnect.dll not found at {path}"},
    "sim_loadfail": {"es": "No se pudo cargar SimConnect.dll: {err}", "en": "Could not load SimConnect.dll: {err}"},
    "sim_exc": {"es": "SimConnect excepción {name} (paquete {pid}, parámetro {idx})",
                "en": "SimConnect exception {name} (packet {pid}, parameter {idx})"},
    "sim_connected": {"es": "Conectado a FSX por SimConnect", "en": "Connected to FSX via SimConnect"},
    "sim_quit": {"es": "FSX se ha cerrado", "en": "FSX has closed"},
    "sim_cmd_err": {"es": "Error en orden SimConnect: {err}", "en": "SimConnect command error: {err}"},
    "sim_read_err": {"es": "Error leyendo SimConnect: {err}", "en": "SimConnect read error: {err}"},
    "sim_restore": {"es": "WeatherSetModeGlobal hr=0x{hr:08X} (el tiempo vuelve al de FSX)",
                    "en": "WeatherSetModeGlobal hr=0x{hr:08X} (weather back to FSX's own)"},
    "sim_sent": {"es": "Tiempo enviado a FSX: {ok}/{n} estaciones{extra}",
                 "en": "Weather sent to FSX: {ok}/{n} stations{extra}"},
    "sim_exc_list": {"es": " | excepciones: {lst}", "en": " | exceptions: {lst}"},
    "sim_noexc": {"es": " | sin excepciones", "en": " | no exceptions"},
    "sim_readback": {"es": "FSX devuelve (petición {req}): {txt}", "en": "FSX returns (request {req}): {txt}"},
    # --- diagnostic ---
    "dg_start": {"es": "DIAG ===== inicio =====", "en": "DIAG ===== start ====="},
    "dg_nonear": {"es": "DIAG FSX no devolvió ninguna estación cercana (¿no tiene estaciones aquí?)",
                  "en": "DIAG FSX returned no nearby station (does it have stations here?)"},
    "dg_station": {"es": "DIAG estación de pruebas: {sid}", "en": "DIAG test station: {sid}"},
    "dg_ok": {"es": "ACEPTADO", "en": "ACCEPTED"},
    "dg_bad": {"es": "RECHAZADO", "en": "REJECTED"},
    "dg_end": {"es": "DIAG ===== fin (FSX queda en modo global) =====",
               "en": "DIAG ===== end (FSX left in global mode) ====="},
    "dg_t1": {"es": "1 con METAR, km", "en": "1 with METAR, km"},
    "dg_t2": {"es": "2 sin METAR, km", "en": "2 without METAR, km"},
    "dg_t3": {"es": "3 sin METAR, millas", "en": "3 without METAR, miles"},
    "dg_t4": {"es": "4 minimo", "en": "4 minimal"},
    "dg_t5": {"es": "5 ejemplo Microsoft", "en": "5 Microsoft example"},
    "dg_g1": {"es": "G1 GLOB sin METAR", "en": "G1 GLOB without METAR"},
    "dg_g2": {"es": "G2 GLOB con METAR", "en": "G2 GLOB with METAR"},
    "dg_g3": {"es": "G3 GLOB ejemplo MS", "en": "G3 GLOB MS example"},
}


def set_lang(lang):
    global _lang
    _lang = lang if lang in SUPPORTED else "es"
    return _lang


def get_lang():
    return _lang


def t(key, **kw):
    s = STR[key][_lang]
    return s.format(**kw) if kw else s

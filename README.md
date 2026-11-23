# FSX Weather Live

Real-world weather for **Microsoft Flight Simulator X (Steam Edition)**, without the dead Microsoft weather servers.

The app downloads free, public **METAR** reports from the NOAA Aviation Weather Center, shows them on a map next to your real aircraft position (read through SimConnect), refreshes every 5 minutes and can inject that weather into FSX.

> Unofficial project. Not affiliated with or endorsed by Microsoft, Valve, NOAA or OpenStreetMap.

## Features

- Map (Leaflet + OpenStreetMap) with nearby METAR stations and a decoded summary of each one.
- Weather for the area you are looking at: pan or zoom anywhere in the world and the airports in view appear, each marked with its ICAO code.
- Search by street address (Nominatim) or ICAO code (e.g. `LEMD`, `KJFK`).
- Live aircraft position and heading from FSX via SimConnect.
- Weather refresh every 5 minutes (configurable) and when you fly far from the last download.
- Optional injection of real weather into FSX (disabled by default; fully reversible).
- Weather symbols on the map for each station (sun/moon, clouds, rain, snow, fog, storm) with temperature and a colour-coded wind arrow.
- Corner panel with the weather at the station nearest your aircraft: condition, temperature, wind, visibility, dew point and QNH.
- English / Spanish interface (toggle in the UI or `"language"` in `config.json`).
- Python standard library only: nothing to install.

## Requirements

- Windows with FSX Steam Edition.
- **32-bit Python 3** ([python.org](https://www.python.org/downloads/windows/), "Windows installer (32-bit)"). FSX's `SimConnect.dll` is 32-bit. Without it the app still runs as a weather map, just without FSX.
- Internet access.

## Install and run

1. Copy the `FSXWeatherLive` folder into your FSX folder, e.g. `E:\SteamLibrary\steamapps\common\FSX\FSXWeatherLive`.
2. Double-click `launch.bat`. The interface opens at <http://localhost:8080>.
3. Start FSX and load a flight; the panel changes to "FSX connected".
4. With the flight loaded, press **Enable** under "FSX injection". Press **Disable** to give FSX its own weather back.

Running from another location? Set `simconnect_dll` in `config.json` to the full path of FSX's `SimConnect.dll`.

## Configuration (`config.json`)

| Key | Default | Meaning |
|---|---|---|
| `language` | `"en"` | `"en"` or `"es"` |
| `port` | `8080` | Local web server port (bound to 127.0.0.1) |
| `update_minutes` | `5` | Download interval |
| `radius_km` / `max_stations` | `250` / `25` | Search radius and number of stations |
| `max_cloud_layers` | `3` | Cloud layers sent per station |
| `default_lat` / `default_lon` | Madrid | Map centre when FSX is not connected |
| `metar_type_keyword` | `false` | See notes below; keep `false` |
| `transition_seconds` | `0` | Seconds FSX takes to phase in each new METAR (`0` = immediately) |
| `freeze_dynamics` | `true` | Stops FSX evolving the injected weather on its own (dynamic update rate 0) |
| `restore_dynamic_rate` | `1` | Dynamic weather rate (0-5) set back when injection is disabled |
| `simconnect_dll` | `"auto"` | `"auto"` = `..\SimConnect.dll`, or a full path |

## Notes on the SimConnect METAR format

FSX does not accept a standard METAR verbatim. Findings so far:

- A leading `METAR` keyword is **rejected** (`WEATHER_INVALID_METAR`); hence `metar_type_keyword: false`.
- Accepted shape: `ICAO DDHHMMZ DDDSSKT[GXX] [DDDVDDD] VIS [wx] clouds TT/DD Qhhhh`, with visibility in `NNKM`, `NSM` or fractions and negative temperatures as `-05`.
- `GLOB` is accepted as the station for global weather.

The **Format diagnostic** button (with injection off) tries several variants and logs which ones FSX accepts. Results appear in the Log panel and in `fsxwl.log`. It leaves FSX in global mode and then tries to put back the global weather FSX had before the test.

While injection is on, the log shows two checks (`+10s` and `+90s`) with the weather FSX really has at the station nearest the aircraft. If they no longer match what was sent, something in FSX overwrote it: avoid opening the FSX Weather dialog, picking a weather theme or turning on FSX real-world weather while injecting.

## Safety

- No FSX file is modified; everything lives in this folder.
- Injection starts disabled, and closing the app (Ctrl+C) with injection on tries to restore FSX's weather.
- POST endpoints require a custom header and a same-origin check, so another website cannot press the buttons.
- Use only one weather program at a time; disable FSX's real-weather option and other injectors.

## Known limits

- Weather is real at each station and FSX interpolates between them.
- Clouds are still drawn by FSX's own engine (no new textures).
- `WEATHER_UNABLE_TO_CREATE_STATION` may appear for stations FSX already has; the per-send summary in the log shows how many exceptions occurred.

## Tests

```
py -3 -m unittest discover -s tests
```

## Data sources

- Weather: [NOAA Aviation Weather Center](https://aviationweather.gov/data/api/)
- Maps and geocoding: [OpenStreetMap](https://www.openstreetmap.org/) / Nominatim

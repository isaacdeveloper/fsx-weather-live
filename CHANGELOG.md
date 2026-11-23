# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.2] - 2026-11-23

### Fixed
- Injected weather seemed to switch back to FSX's default right after enabling injection: each METAR was sent with a 10-minute phase-in (`Seconds = 600`), so FSX kept showing its own weather while it slowly blended. It is now applied immediately (`transition_seconds`, default `0`).
- FSX's dynamic weather could drift the injected conditions; the dynamic update rate is set to 0 while injecting and given back afterwards (`freeze_dynamics`, `restore_dynamic_rate`).
- Disabling injection no longer tries to remove stations that already existed in FSX (dozens of `WEATHER_UNABLE_TO_REMOVE_STATION` in the log): only stations the app really created are removed.
- The format diagnostic no longer leaves the test weather as FSX's global weather; it puts back the original GLOB observation.

### Added
- Readback checks 10 s and 90 s after each injection log what FSX actually has near the aircraft.

## [0.3.1] - 2026-11-22

### Added
- Clicking an airport on the map (or in the nearby-stations list) puts its ICAO code in the search box.

## [0.3.0] - 2026-11-22

### Added
- The map loads the weather for whatever area is on screen: panning or zooming anywhere in the world fetches the METAR airports in view (refreshed every `update_minutes` too).
- Every weather marker now shows the airport's ICAO code.
- Airports are thinned to one per grid cell (international airports preferred) so the map stays readable when zoomed out.
- `GET /api/area?s=&w=&n=&e=` endpoint, with a 5-minute cache and support for views that cross the date line.

### Fixed
- A diagnostic test depended on test execution order for its language.

## [0.2.1] - 2026-11-22

### Changed
- Launcher renamed from `iniciar.bat` to `launch.bat`, with English-only messages.
- English is now the default language (`"language": "en"`); Spanish is still available from the UI toggle or `config.json`.
- README updated with the new map features; code comments and docstrings translated to English.

### Removed
- Spanish documentation (`README.es.md`, `LEEME.txt`); the project docs are English-only.

## [0.2.0] - 2026-11-22

### Added
- Weather symbols on the map: each station shows an icon (sun/moon, clouds, rain, snow, fog, storm), temperature and a wind arrow with speed/gusts, colour-coded by strength.
- Corner panel (top right, collapsible) with the weather at the station nearest the aircraft: condition, temperature, wind, visibility, dew point and QNH.
- `weather` object (condition category + key values) in each station of `/api/state` and `/api/search`.

## [0.1.1]

### Added
- English translation of the whole app (UI and backend messages) with an ES/EN toggle and a `language` option in `config.json`.
- `POST /api/lang` endpoint.
- "Format diagnostic" button that probes which METAR variants FSX accepts.
- English `README.md` and this changelog; Spanish docs moved to `README.es.md`.

### Changed
- Aircraft icon is now an SVG pointing north, so the heading matches (the ✈ glyph is rotated ~45° in many fonts).
- Exceptions raised while sending weather are summarised in one log line per send instead of one line each.

### Fixed
- FSX rejected every METAR with `WEATHER_INVALID_METAR`: the leading `METAR` keyword is no longer sent (`metar_type_keyword` is `false` by default).
- Custom weather mode is re-enabled after a reconnect, and a stale restore can no longer switch FSX back to global mode.
- Crash when the NOAA response contained non-object items.
- Fractional visibility such as `1 1/2SM` was rounded down.

## [0.1.0]

### Added
- Initial release: NOAA METAR download, Leaflet map, address/ICAO search, live aircraft position through SimConnect, 5-minute refresh and optional weather injection into FSX.

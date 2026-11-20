# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

# FSX Weather Live

Tiempo real para **Microsoft Flight Simulator X (edición Steam)**, sin los servidores meteorológicos de Microsoft (ya apagados).

La app descarga **METAR** públicos y gratuitos del NOAA Aviation Weather Center, los muestra en un mapa junto a la posición real de tu avión (leída por SimConnect), se actualiza cada 5 minutos y puede inyectar ese tiempo en FSX.

*English version: [README.md](README.md)*

> Proyecto no oficial. Sin relación con Microsoft, Valve, NOAA ni OpenStreetMap.

## Requisitos

- Windows con FSX Steam.
- **Python 3 de 32 bits** (python.org, "Windows installer (32-bit)"): el `SimConnect.dll` de FSX es de 32 bits. Sin él la app funciona solo como mapa.
- Conexión a internet.

## Uso

1. Copia la carpeta `FSXWeatherLive` dentro de la de FSX.
2. Doble clic en `iniciar.bat` (abre http://localhost:8080).
3. Arranca FSX y carga un vuelo.
4. Con el vuelo cargado, pulsa **Activar** en "Inyección en FSX". **Desactivar** devuelve a FSX su tiempo.

Si la ejecutas desde otra ruta, pon en `config.json` la ruta completa de `SimConnect.dll` en `simconnect_dll`.

## Idioma

Botón EN/ES en la interfaz, o `"language": "es"` / `"en"` en `config.json`.

## Notas

- FSX rechaza la palabra `METAR` al inicio de la cadena (`WEATHER_INVALID_METAR`), por eso `metar_type_keyword` es `false`.
- El botón "Diagnóstico de formato" (con la inyección desactivada) prueba variantes y anota en el Registro cuáles acepta FSX; deja FSX en modo global con un tiempo de prueba.
- No se modifica ningún fichero de FSX. Usa un solo programa de tiempo a la vez.

Más detalles técnicos en [README.md](README.md). Pruebas: `py -3 -m unittest discover -s tests`.

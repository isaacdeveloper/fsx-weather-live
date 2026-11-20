@echo off
rem FSX Weather Live - launcher / lanzador. Needs 32-bit Python (FSX's SimConnect.dll is 32-bit).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3-32 -c "print()" >nul 2>nul
  if %errorlevel%==0 (
    start "" http://localhost:8080
    py -3-32 run.py
    goto :fin
  )
)
echo 32-bit Python not found. Only the map will open, without FSX connection.
echo No encuentro Python de 32 bits. Se abre solo el mapa, sin conexion con FSX.
echo Install 32-bit Python 3 from python.org to connect to FSX.
echo Instala Python 3 de 32 bits desde python.org si quieres conectar con FSX.
start "" http://localhost:8080
python run.py
:fin
pause

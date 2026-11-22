@echo off
rem FSX Weather Live launcher. Needs 32-bit Python (FSX's SimConnect.dll is 32-bit).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3-32 -c "print()" >nul 2>nul
  if %errorlevel%==0 (
    start "" http://localhost:8080
    py -3-32 run.py
    goto :end
  )
)
echo 32-bit Python not found. Only the map will open, without FSX connection.
echo Install 32-bit Python 3 from python.org to connect to FSX.
start "" http://localhost:8080
python run.py
:end
pause

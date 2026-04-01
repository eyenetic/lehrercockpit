@echo off
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 agent_server.py --mode windows
  goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
  python agent_server.py --mode windows
  goto :eof
)

echo Python 3 wurde nicht gefunden.
echo Bitte Python 3 installieren und den Agenten erneut starten.
pause

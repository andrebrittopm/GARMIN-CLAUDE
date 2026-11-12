@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py garmin_painel.py %*) else (python garmin_painel.py %*)
echo.
pause

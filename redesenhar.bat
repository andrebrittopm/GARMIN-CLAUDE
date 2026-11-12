@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py garmin_painel.py --so-visual %*) else (python garmin_painel.py --so-visual %*)
echo.
pause

@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py garmin_painel.py %*) || (python garmin_painel.py %*)
echo.
pause

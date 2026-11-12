@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py garmin_painel.py --sem-abrir --notificar > ultimo_log.txt 2>&1) else (python garmin_painel.py --sem-abrir --notificar > ultimo_log.txt 2>&1)

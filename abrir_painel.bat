@echo off
cd /d "%~dp0"
echo Abrindo o painel com edicao (so neste computador). Feche esta janela para encerrar.
where py >nul 2>nul
if %errorlevel%==0 (py garmin_painel.py --servir) else (python garmin_painel.py --servir)
echo.
pause

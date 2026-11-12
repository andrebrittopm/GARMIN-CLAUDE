@echo off
cd /d "%~dp0"
echo Atualizando o PROGRAMA (seus dados, fotos e logos nao serao tocados)...
where py >nul 2>nul
if %errorlevel%==0 (py garmin_painel.py --atualizar-programa) else (python garmin_painel.py --atualizar-programa)
echo.
pause

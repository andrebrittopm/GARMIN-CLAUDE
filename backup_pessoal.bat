@echo off
cd /d "%~dp0"
echo Criando a copia de seguranca dos seus arquivos pessoais (perfil, provas, plano, fotos e logos)...
where py >nul 2>nul
if %errorlevel%==0 (py garmin_painel.py --backup-pessoal) else (python garmin_painel.py --backup-pessoal)
echo.
pause

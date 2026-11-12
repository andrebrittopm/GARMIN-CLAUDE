@echo off
cd /d "%~dp0"
echo Criando a atualizacao automatica (a cada 6 horas, so com voce logado no Windows)...
schtasks /Create /TN "PainelGarmin" /SC HOURLY /MO 6 /ST 07:00 /TR "\"%~dp0atualizar_silencioso.bat\"" /F
if errorlevel 1 (echo ERRO ao criar a tarefa.) else (echo Pronto. Para desligar, de dois cliques em remover_agendamento.bat)
echo.
pause

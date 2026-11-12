"""Notificação do Windows (balão na área de notificações), sem programas extras.

Usa o PowerShell que já vem no Windows. O texto vai por variável de ambiente (nunca
dentro do comando), então nada digitado aqui vira comando. Fora do Windows não faz nada.
Mensagens são sempre seguras: sem chave, token ou detalhes técnicos.
"""
import base64
import os
import subprocess
import sys

SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
if ($env:PAINEL_NOTIF_NIVEL -eq 'erro') { $n.Icon = [System.Drawing.SystemIcons]::Error }
elseif ($env:PAINEL_NOTIF_NIVEL -eq 'aviso') { $n.Icon = [System.Drawing.SystemIcons]::Warning }
else { $n.Icon = [System.Drawing.SystemIcons]::Information }
$n.BalloonTipTitle = $env:PAINEL_NOTIF_TITULO
$n.BalloonTipText = $env:PAINEL_NOTIF_TEXTO
$n.Visible = $true
$n.ShowBalloonTip(15000)
Start-Sleep -Seconds 17
$n.Dispose()
"""


def construir(titulo, texto, nivel="info"):
    """(argumentos, ambiente) do comando. Testável em qualquer sistema."""
    codificado = base64.b64encode(SCRIPT.encode("utf-16-le")).decode("ascii")
    args = ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-EncodedCommand", codificado]
    env = {**os.environ,
           "PAINEL_NOTIF_TITULO": " ".join(str(titulo).split())[:60],
           "PAINEL_NOTIF_TEXTO": " ".join(str(texto).split())[:230],
           "PAINEL_NOTIF_NIVEL": nivel if nivel in ("erro", "aviso", "info") else "info"}
    return args, env


def notificar(titulo, texto, nivel="info"):
    """Mostra o balão sem esperar. Devolve True se disparou (só no Windows)."""
    if sys.platform != "win32":
        return False
    args, env = construir(titulo, texto, nivel)
    try:
        subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=0x08000000)   # sem janela
        return True
    except OSError:
        return False

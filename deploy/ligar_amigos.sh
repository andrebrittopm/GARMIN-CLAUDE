#!/usr/bin/env bash
# Liga o painel dos AMIGOS: uma página sem dados de saúde, GPS, calendário ou plano, num link público secreto
# (Tailscale Funnel, porta 10000, só esta página). O seu painel completo continua só na rede Tailscale (porta 8443).
set -euo pipefail
principal() {
  [ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
  AQUI=/opt/painel-garmin
  install -m 0644 "$AQUI/deploy/painel-garmin-amigos.service" /etc/systemd/system/
  systemctl daemon-reload
  bash "$AQUI/deploy/rodar.sh" --amigos-ligar --sem-abrir
  systemctl enable --now painel-garmin-amigos.service
  sleep 1
  systemctl is-active painel-garmin-amigos.service
  tailscale funnel --bg --https=10000 http://127.0.0.1:8766 || \
    echo "AVISO: o 'tailscale funnel' não concluiu. Se pediu para ativar o Funnel, abra o link que ele mostrou, ative e rode este script de novo."
  echo
  echo "Endereço para enviar aos amigos (guarde: quem tem o link vê a página):"
  bash "$AQUI/deploy/rodar.sh" --amigos-endereco
}
principal "$@"
exit $?

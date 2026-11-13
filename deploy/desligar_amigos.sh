#!/usr/bin/env bash
# Desliga o painel dos amigos: tira do ar o link público, para o serviço e apaga link e página.
set -euo pipefail
principal() {
  [ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
  tailscale funnel --https=10000 off || true
  systemctl disable --now painel-garmin-amigos.service 2>/dev/null || true
  bash /opt/painel-garmin/deploy/rodar.sh --amigos-desligar
  echo "Painel dos amigos desligado."
}
principal "$@"
exit $?

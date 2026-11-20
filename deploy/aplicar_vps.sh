#!/usr/bin/env bash
# Aplica na VPS o código que já está em /opt/painel-garmin (permissões, serviços, chaves) e reinicia o painel.
# Não baixa nada. Usado por atualizar_vps.sh e pela atualização automática.
set -euo pipefail
principal() {
  [ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
  cd /opt/painel-garmin
  chown -R root:root /opt/painel-garmin
  chmod -R go-w /opt/painel-garmin
  install -m 0644 deploy/painel-garmin.service deploy/painel-garmin-atualizar.service deploy/painel-garmin-atualizar.timer \
    deploy/painel-garmin-amigos.service deploy/painel-garmin-autoatualizar.service deploy/painel-garmin-autoatualizar.timer /etc/systemd/system/
  bash deploy/ligar_credenciais.sh
  systemctl daemon-reload
  systemctl restart painel-garmin.service
  if systemctl is-enabled painel-garmin-amigos.service >/dev/null 2>&1; then systemctl restart painel-garmin-amigos.service; fi
}
principal "$@"
exit $?

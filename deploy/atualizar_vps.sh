#!/usr/bin/env bash
# Atualiza o PROGRAMA na VPS a partir do GitHub (seus dados e chaves não são tocados) e reinicia o painel.
set -euo pipefail

principal() {      # tudo dentro de uma função: o bash lê o corpo inteiro antes de rodar, então
                   # trocar este próprio arquivo durante a atualização não o corrompe
  [ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
  cd /opt/painel-garmin
  git -c safe.directory=/opt/painel-garmin fetch --quiet origin
  git -c safe.directory=/opt/painel-garmin merge --ff-only FETCH_HEAD
  chown -R root:root /opt/painel-garmin
  chmod -R go-w /opt/painel-garmin
  install -m 0644 deploy/painel-garmin.service deploy/painel-garmin-atualizar.service deploy/painel-garmin-atualizar.timer /etc/systemd/system/
  bash deploy/ligar_credenciais.sh
  systemctl daemon-reload
  systemctl restart painel-garmin.service
  echo "Programa atualizado: $(git -c safe.directory=/opt/painel-garmin rev-parse --short HEAD)"
}
principal "$@"
exit $?

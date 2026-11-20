#!/usr/bin/env bash
# Atualiza o PROGRAMA na VPS a partir do GitHub (seus dados e chaves não são tocados) e reinicia o painel.
# Manual e sem a trava dos testes; a atualização automática (autoatualizar.py) confere os testes antes.
set -euo pipefail

principal() {      # tudo dentro de uma função: o bash lê o corpo inteiro antes de rodar, então
                   # trocar este próprio arquivo durante a atualização não o corrompe
  [ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
  cd /opt/painel-garmin
  git -c safe.directory=/opt/painel-garmin fetch --quiet origin
  git -c safe.directory=/opt/painel-garmin merge --ff-only FETCH_HEAD
  bash deploy/aplicar_vps.sh
  echo "Programa atualizado: $(git -c safe.directory=/opt/painel-garmin rev-parse --short HEAD)"
}
principal "$@"
exit $?

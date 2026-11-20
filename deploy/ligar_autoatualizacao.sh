#!/usr/bin/env bash
# Liga a atualização automática do programa (2x por dia, só com testes do GitHub aprovados, com volta atrás).
set -euo pipefail
principal() {
  [ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
  bash /opt/painel-garmin/deploy/aplicar_vps.sh
  systemctl enable --now painel-garmin-autoatualizar.timer
  systemctl list-timers painel-garmin-autoatualizar.timer --no-pager
  echo "Atualização automática do programa LIGADA. Para desligar: bash /opt/painel-garmin/deploy/desligar_autoatualizacao.sh"
}
principal "$@"
exit $?

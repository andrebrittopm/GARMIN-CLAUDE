#!/usr/bin/env bash
# Desliga a atualização automática do programa (os dados continuam sendo atualizados normalmente).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
systemctl disable --now painel-garmin-autoatualizar.timer
echo "Atualização automática do programa DESLIGADA."

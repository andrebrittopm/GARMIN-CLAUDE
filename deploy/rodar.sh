#!/usr/bin/env bash
# Roda o programa do painel como o serviço roda (mesmo usuário, mesmas chaves, mesmas travas).
# Exemplos:  bash rodar.sh --teste   |   bash rodar.sh --sem-abrir   |   bash rodar.sh --diagnostico
set -euo pipefail
[ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
CRED=()
for ID in garmin-personal-api-key intervals-icu-api-key; do
  [ -f "/etc/credstore.encrypted/$ID.cred" ] && CRED+=(-p "LoadCredentialEncrypted=$ID:/etc/credstore.encrypted/$ID.cred")
done
exec systemd-run --quiet --wait --pipe --collect \
  -p User=painel -p Group=painel -p StateDirectory=painel-garmin -p StateDirectoryMode=0750 \
  -p WorkingDirectory=/opt/painel-garmin "${CRED[@]}" \
  -p Environment=GARMIN_PAINEL_PASTA_DADOS=/var/lib/painel-garmin -p Environment=PYTHONDONTWRITEBYTECODE=1 \
  -p NoNewPrivileges=yes -p PrivateTmp=yes -p ProtectSystem=strict -p ProtectHome=yes \
  /usr/bin/python3 /opt/painel-garmin/garmin_painel.py "$@"

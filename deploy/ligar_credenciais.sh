#!/usr/bin/env bash
# Liga aos serviços do painel as chaves que já foram guardadas (criptografadas) em /etc/credstore.encrypted.
# Cria um arquivo de configuração por chave existente (e apaga o de chave que não existe mais).
# Rodado sozinho por guardar_chave.sh, instalar_vps.sh e atualizar_vps.sh.
set -euo pipefail
if [ "$(id -u)" -ne 0 ] && [ -z "${PAINEL_TESTE:-}" ]; then exec sudo bash "$0" "$@"; fi
CRED_DIR="${PAINEL_CREDSTORE:-/etc/credstore.encrypted}"
UNIT_DIR="${PAINEL_UNIT_DIR:-/etc/systemd/system}"
for ID in garmin-personal-api-key intervals-icu-api-key; do
  ARQ="$CRED_DIR/$ID.cred"
  for U in painel-garmin.service painel-garmin-atualizar.service; do
    D="$UNIT_DIR/$U.d"
    if [ -f "$ARQ" ]; then
      install -d -m 0755 "$D"
      printf '[Service]\nLoadCredentialEncrypted=%s:%s\n' "$ID" "$ARQ" > "$D/cred-$ID.conf"
      chmod 0644 "$D/cred-$ID.conf"
    else
      rm -f "$D/cred-$ID.conf"
    fi
  done
done
if [ -z "${PAINEL_TESTE:-}" ]; then
  systemctl daemon-reload
  systemctl try-restart painel-garmin.service 2>/dev/null || true
fi

#!/usr/bin/env bash
# Guarda uma chave CRIPTOGRAFADA pelo sistema (systemd-creds). Você digita/cola a chave aqui;
# ela não aparece na tela, não vai para o histórico e não fica em arquivo legível.
# Uso: bash guardar_chave.sh garmin      ou      bash guardar_chave.sh intervals
set -euo pipefail
erro() { echo "ERRO: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || exec sudo bash "$0" "$@"
case "${1:-}" in
  garmin) ID=garmin-personal-api-key ;;
  intervals) ID=intervals-icu-api-key ;;
  *) erro "use: guardar_chave.sh garmin   ou   guardar_chave.sh intervals" ;;
esac
if [ "${2:-}" = "--stdin" ]; then
  # a chave chega pela entrada padrão (enviada pelo programa do Windows via ssh): sem colar, sem tela
  IFS= read -r K || true
  K="${K%$'\r'}"
else
  read -r -s -p "Cole a chave ($1) e aperte Enter (nada aparece na tela): " K
  echo
fi
if [ "${#K}" -lt 10 ]; then
  N="${#K}"; unset K
  erro "recebi só $N caracteres (a chave tem mais de 100). A colagem não chegou aqui. Nada foi guardado."
fi
case "$K" in *[[:space:]]*) erro "a chave não pode ter espaços. Nada foi guardado." ;; esac
ARQ="/etc/credstore.encrypted/$ID.cred"
install -d -m 0700 /etc/credstore.encrypted
printf '%s' "$K" | systemd-creds encrypt --name="$ID" - "$ARQ" || { unset K; erro "não consegui criptografar."; }
unset K
chmod 0600 "$ARQ"
systemd-creds decrypt --name="$ID" "$ARQ" - >/dev/null 2>&1 || erro "a chave foi gravada, mas não consegui abrir de volta."
echo "OK: chave '$1' guardada criptografada em $ARQ ($(stat -c %s "$ARQ") bytes)."
bash "$(dirname "${BASH_SOURCE[0]}")/ligar_credenciais.sh"

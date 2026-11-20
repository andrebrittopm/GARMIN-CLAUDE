#!/usr/bin/env bash
# Revoga TODAS as chaves de automação (as linhas "painel-automacao" do authorized_keys). Suas outras chaves ficam.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || [ -n "${PAINEL_TESTE:-}" ] || exec sudo bash "$0" "$@"
ARQ="${PAINEL_AUTHORIZED:-/root/.ssh/authorized_keys}"
[ -f "$ARQ" ] || { echo "Nada a remover."; exit 0; }
ANTES="$(wc -l < "$ARQ")"
grep -v ' painel-automacao$' "$ARQ" > "$ARQ.novo" || true
chmod 600 "$ARQ.novo"; mv "$ARQ.novo" "$ARQ"
echo "Removidas: $(( ANTES - $(wc -l < "$ARQ") )) chave(s) de automação."

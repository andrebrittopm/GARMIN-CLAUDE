#!/usr/bin/env bash
# Autoriza uma chave PÚBLICA de automação que só pode rodar as ações de comando_remoto.sh (sem terminal).
# Uso:  type id_ed25519_painel_auto.pub | ssh root@IP "bash /opt/painel-garmin/deploy/instalar_chave_automacao.sh"
# A chave pública não é segredo. Para revogar: bash remover_chave_automacao.sh
set -euo pipefail
erro() { echo "ERRO: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || [ -n "${PAINEL_TESTE:-}" ] || exec sudo bash "$0" "$@"
ARQ="${PAINEL_AUTHORIZED:-/root/.ssh/authorized_keys}"
IFS= read -r LINHA || true
LINHA="${LINHA%$'\r'}"
[[ "$LINHA" =~ ^ssh-ed25519\ AAAA[A-Za-z0-9+/]{20,}={0,2}(\ [A-Za-z0-9._@-]{0,60})?$ ]] || erro "isso não parece uma chave pública ssh-ed25519 (uma linha só)."
CHAVE="$(printf '%s' "$LINHA" | cut -d' ' -f1,2)"
mkdir -p "$(dirname "$ARQ")"; chmod 700 "$(dirname "$ARQ")" 2>/dev/null || true
touch "$ARQ"; chmod 600 "$ARQ"
if grep -qF "$CHAVE" "$ARQ"; then erro "essa chave já está autorizada (nada foi alterado)."; fi
CMD="${PAINEL_COMANDO:-/opt/painel-garmin/deploy/comando_remoto.sh}"
printf 'command="%s",restrict %s painel-automacao\n' "$CMD" "$CHAVE" >> "$ARQ"
echo "OK: chave de automação autorizada (só as ações do comando_remoto.sh, sem terminal)."

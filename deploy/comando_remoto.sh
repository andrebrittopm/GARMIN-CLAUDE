#!/usr/bin/env bash
# COMANDO FORÇADO da chave de automação ("painel-automacao"): quem entra com essa chave NÃO ganha um terminal;
# só consegue pedir uma das ações abaixo, e nada além disso. Não há como passar outros argumentos nem comandos.
# O link dos amigos e as chaves da Garmin/intervals.icu nunca são mostrados por nenhuma destas ações.
set -euo pipefail
DIR="${PAINEL_DIR:-/opt/painel-garmin}"
CMD="${SSH_ORIGINAL_COMMAND:-}"

negar() { echo "NEGADO: comando não permitido. Ações: status, logs, diagnostico, atualizar-dados, atualizar-dados-rotas, atualizar-programa, amigos-modo basico|completo, amigos-desligar" >&2; exit 126; }

# só letras minúsculas, números, espaço e hífen (sem ; | & $ ` aspas, quebra de linha, barras ou pontos)
[[ "$CMD" =~ ^[a-z0-9\ -]{1,60}$ ]] || negar

case "$CMD" in
  status)
    echo "== serviços"
    for u in painel-garmin.service painel-garmin-atualizar.timer painel-garmin-autoatualizar.timer painel-garmin-amigos.service; do
      printf '%s: %s\n' "$u" "$(systemctl is-active "$u" 2>/dev/null || true)"
    done
    echo "== próximas execuções"
    systemctl list-timers 'painel-garmin-*' --no-pager 2>/dev/null || true
    echo "== versão do programa"
    git -c safe.directory="$DIR" -C "$DIR" log -1 --format='%h %ad %s' --date=short 2>/dev/null || true
    echo "== disco dos dados"
    df -h /var/lib/painel-garmin 2>/dev/null | tail -1 || true
    ;;
  logs)
    journalctl -u painel-garmin-atualizar.service -u painel-garmin.service -u painel-garmin-autoatualizar.service -n 40 --no-pager
    ;;
  diagnostico) exec bash "$DIR/deploy/rodar.sh" --diagnostico ;;
  atualizar-dados) exec bash "$DIR/deploy/rodar.sh" --sem-abrir ;;
  atualizar-dados-rotas) exec bash "$DIR/deploy/rodar.sh" --rotas --sem-abrir ;;
  atualizar-programa) exec python3 "$DIR/deploy/autoatualizar.py" --agora ;;
  "amigos-modo basico") exec bash "$DIR/deploy/rodar.sh" --amigos-modo basico ;;
  "amigos-modo completo") exec bash "$DIR/deploy/rodar.sh" --amigos-modo completo ;;
  amigos-desligar) exec bash "$DIR/deploy/desligar_amigos.sh" ;;
  *) negar ;;
esac

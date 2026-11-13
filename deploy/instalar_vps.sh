#!/usr/bin/env bash
# Instala o Painel Garmin nesta VPS (Ubuntu 24.04), acessível SÓ pela sua rede Tailscale.
# Não mexe em nginx, portas 80/443/8090 nem em nada do que já roda na VPS.
# Pode ser rodado de novo sem problema (não apaga seus dados nem as chaves).
set -euo pipefail

erro() { echo "ERRO: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || erro "rode como root."
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ "$AQUI" = "/opt/painel-garmin" ] || erro "o programa deve estar em /opt/painel-garmin (está em $AQUI)."
for c in python3 systemctl systemd-creds tailscale; do
  command -v "$c" >/dev/null || erro "não encontrei '$c'."
done
tailscale status >/dev/null 2>&1 || erro "o Tailscale não está conectado (rode: tailscale up)."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || erro "precisa do Python 3.9 ou mais novo."

DADOS=/var/lib/painel-garmin
echo "1/5 Usuário e pastas"
id -u painel >/dev/null 2>&1 || useradd --system --home-dir "$DADOS" --shell /usr/sbin/nologin painel
install -d -o painel -g painel -m 0750 "$DADOS"
install -d -o root -g root -m 0700 /etc/credstore.encrypted
# o programa pertence ao root: o serviço só lê (não consegue alterar o próprio código)
chown -R root:root "$AQUI"
chmod -R go-w "$AQUI"

echo "2/5 Cofre de chaves do sistema"
systemd-creds setup >/dev/null 2>&1 || true

echo "3/5 Serviços"
install -m 0644 "$AQUI"/deploy/painel-garmin.service "$AQUI"/deploy/painel-garmin-atualizar.service \
  "$AQUI"/deploy/painel-garmin-atualizar.timer "$AQUI"/deploy/painel-garmin-amigos.service /etc/systemd/system/
bash "$AQUI/deploy/ligar_credenciais.sh"
systemctl daemon-reload
systemctl enable --now painel-garmin.service
systemctl enable --now painel-garmin-atualizar.timer

echo "4/5 Acesso pelo Tailscale (porta 8443, só seus aparelhos)"
tailscale serve --bg --https=8443 http://127.0.0.1:8765 || \
  echo "AVISO: o 'tailscale serve' não concluiu. Se pediu para ativar HTTPS/MagicDNS, ative no painel de administração do Tailscale e rode este script de novo."

echo "5/5 Conferência"
sleep 2
systemctl is-active painel-garmin.service painel-garmin-atualizar.timer || true
echo
echo "Pronto. Próximos passos (veja deploy/LEIA-ME.md):"
echo "  1) bash $AQUI/deploy/guardar_chave.sh garmin   (ou, do Windows: py garmin_painel.py --enviar-chave garmin --para root@IP)"
echo "  2) bash $AQUI/deploy/rodar.sh --teste       (confere a chave com 1 dia de dados)"
echo "  3) bash $AQUI/deploy/rodar.sh --sem-abrir   (primeira atualização completa)"
echo "  4) bash $AQUI/deploy/rodar.sh --endereco    (mostra o endereço do painel)"

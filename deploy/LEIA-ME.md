# Painel Garmin na VPS (Ubuntu 24.04, acesso só pelo Tailscale)

O painel roda como um usuário comum (`painel`), na porta interna 8765 (só dentro da VPS). O Tailscale o entrega aos
seus aparelhos em `https://<nome>.ts.net:8443`. Nada novo fica aberto na internet. O nginx, as portas 80/443/8090 e o
Mais Delivery não são tocados.

## Instalar (uma vez, como root, na VPS)
```
git clone --branch claude/garmin-data-dashboard-fi7vqq --single-branch https://github.com/andrebrittopm/GARMIN-CLAUDE.git /opt/painel-garmin
bash /opt/painel-garmin/deploy/instalar_vps.sh
```
No painel de administração do Tailscale (login.tailscale.com > DNS), deixe **MagicDNS** e **HTTPS Certificates** ligados.

## Guardar as chaves (criptografadas pelo sistema)
```
bash /opt/painel-garmin/deploy/guardar_chave.sh garmin
bash /opt/painel-garmin/deploy/guardar_chave.sh intervals     # opcional
```
A chave é digitada/colada num campo escondido, vai direto para `systemd-creds` e fica em `/etc/credstore.encrypted/`
(criptografada com a chave da própria máquina). Só os serviços do painel conseguem abri-la.

## Usar
```
bash /opt/painel-garmin/deploy/rodar.sh --teste            # confere a chave com 1 dia de dados
bash /opt/painel-garmin/deploy/rodar.sh --sem-abrir        # primeira atualização
bash /opt/painel-garmin/deploy/rodar.sh --endereco         # mostra o endereço (com a senha) para abrir no navegador
bash /opt/painel-garmin/deploy/rodar.sh --diagnostico      # conferência geral
```
A atualização automática roda às 01h, 07h, 13h e 19h (`systemctl list-timers painel-garmin-atualizar.timer`).

## Trazer seus dados do Windows (provas, perfil, fotos, plano, histórico)
No Windows: `py garmin_painel.py --backup-pessoal --com-dados` e envie o ZIP para a pasta de dados da VPS:
```
scp backups_pessoais\ARQUIVO.zip root@IP_DA_VPS:/var/lib/painel-garmin/
```
Na VPS (o ZIP precisa pertencer ao usuário `painel`):
```
chown painel:painel /var/lib/painel-garmin/ARQUIVO.zip
bash /opt/painel-garmin/deploy/rodar.sh --restaurar-backup /var/lib/painel-garmin/ARQUIVO.zip
rm /var/lib/painel-garmin/ARQUIVO.zip
```
O ZIP com `--com-dados` tem dados de saúde e de localização: apague-o depois de restaurar.

## Atualizar o programa
```
bash /opt/painel-garmin/deploy/atualizar_vps.sh
```
Atualiza o código pelo GitHub e reinicia o painel. Dados e chaves não são tocados.

## Desligar
```
tailscale serve reset
systemctl disable --now painel-garmin.service painel-garmin-atualizar.timer
```

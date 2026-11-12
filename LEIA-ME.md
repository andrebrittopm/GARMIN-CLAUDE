# Painel Garmin

Painel pessoal feito com a Garmin Connect Personal API (chave oficial).
Só lê dados; não altera nada na conta. A chave fica no cofre do sistema
(Gerenciador de Credenciais do Windows ou Chaves do Mac), com o nome
`garmin-personal-api-key`, e nunca é gravada em arquivo.

Guia completo em português (para quem não programa): **GUIA.md**.

## Arquivos
- `garmin_painel.py` busca os dados; `formatos.py`, `visual.py` desenham o painel;
  `cofre.py` (chave e token), `armazem.py` (dados e backups), `diagnostico.py` e
  `configuracao.py` (vencimento da chave).
- `atualizar.bat`: atualiza e abre o painel. `redesenhar.bat`: só refaz o visual
  com os dados já guardados (sem internet, sem chave).
- `agendar.bat` / `remover_agendamento.bat`: atualização automática a cada 6 horas
  (só com você logado no Windows). O resultado fica em `ultimo_log.txt`.

## Comandos
- Testar com 1 dia: `py garmin_painel.py --teste`
- Atualizar: `py garmin_painel.py` (`--dias 60` para período maior)
- Redesenhar sem consultar a Garmin: `py garmin_painel.py --so-visual`
- Apagar o token guardado no cofre: `py garmin_painel.py --esquecer-token`
- Metas suas: `py garmin_painel.py --meta km-mes=50` (opções: km-semana, corridas-semana, km-mes, horas-mes); apagar: `--remover-meta NOME`
- Mais histórico para os recordes: `py garmin_painel.py --historico 365`
- Visual de corredor (foto, provas, logos): `py garmin_painel.py --criar-perfil` e edite `perfil.txt` e `provas.txt`
- Conferir tudo (chave, token, conexão, dados, agendamento): `py garmin_painel.py --diagnostico`
- Avisar antes de a chave vencer: `py garmin_painel.py --chave-vence AAAA-MM-DD`

## Onde ficam seus dados
- `painel.html` e `dados_brutos.json` (dados de saúde, sem chave nem token) ficam só
  neste computador e estão fora do GitHub (`.gitignore`).
- O token (vale 24 h) é guardado no cofre do Windows como `garmin-personal-api-token`.

## Teste automático (servidor falso, sem chave)
`python tests/test_painel.py` (roda também sozinho no GitHub a cada envio)

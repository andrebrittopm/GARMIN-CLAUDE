# Painel Garmin

Painel pessoal feito com a Garmin Connect Personal API (chave oficial).
Só lê dados; não altera nada na conta. A chave fica no cofre do sistema
(Gerenciador de Credenciais do Windows ou Chaves do Mac), com o nome
`garmin-personal-api-key`, e nunca é gravada em arquivo.

## Arquivos
- `garmin_painel.py` busca os dados; `formatos.py`, `visual.py` desenham o painel;
  `cofre.py` (chave e token) e `armazem.py` (dados guardados).
- `atualizar.bat`: atualiza e abre o painel. `redesenhar.bat`: só refaz o visual
  com os dados já guardados (sem internet, sem chave).
- `agendar.bat` / `remover_agendamento.bat`: atualização automática a cada 6 horas
  (só com você logado no Windows). O resultado fica em `ultimo_log.txt`.

## Comandos
- Testar com 1 dia: `py garmin_painel.py --teste`
- Atualizar: `py garmin_painel.py` (`--dias 60` para período maior)
- Redesenhar sem consultar a Garmin: `py garmin_painel.py --so-visual`
- Apagar o token guardado no cofre: `py garmin_painel.py --esquecer-token`

## Onde ficam seus dados
- `painel.html` e `dados_brutos.json` (dados de saúde, sem chave nem token) ficam só
  neste computador e estão fora do GitHub (`.gitignore`).
- O token (vale 24 h) é guardado no cofre do Windows como `garmin-personal-api-token`.

## Teste automático (servidor falso, sem chave)
`python tests/test_painel.py`

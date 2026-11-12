"""`py garmin_painel.py --diagnostico`: confere o painel de ponta a ponta.

Mostra [OK], [ATENCAO] ou [FALHA] para cada item. Nunca imprime a chave nem o
token (só tamanhos e prazos). Faz no máximo UMA leitura na Garmin (perfil do
usuário), só para provar que chave, token e internet funcionam; o conteúdo da
resposta é descartado.
"""
import datetime as dt
import os
import subprocess
import sys
import time

import armazem
import configuracao

NOME_TAREFA = "PainelGarmin"


def comando_ok(args):
    """True se o comando terminou com sucesso. A resposta dele é descartada:
    o Windows responde em código de página local (acentos) e não precisamos dela."""
    try:
        return subprocess.run(args, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return None


def _idade(segundos):
    h = int(segundos // 3600)
    if h < 1:
        return f"{int(segundos // 60)} min"
    if h < 48:
        return f"{h} h"
    return f"{h // 24} dias"


def executar():
    import garmin_painel as gp            # import tardio (evita ciclo)
    cont = {"falha": 0, "atencao": 0}

    def ok(m):
        print(f"[OK]       {m}")

    def atencao(m):
        cont["atencao"] += 1
        print(f"[ATENCAO]  {m}")

    def falha(m):
        cont["falha"] += 1
        print(f"[FALHA]    {m}")

    print("Diagnóstico do painel Garmin\n")
    ok(f"Python {sys.version.split()[0]}")
    pasta = gp.pasta_dados()
    ok(f"Pasta dos dados: {pasta}")

    # --- chave
    chave = None
    try:
        chave = gp.ler_chave()
        ok(f"Chave encontrada no cofre ({len(chave)} caracteres)")
        if len(chave) < 129:
            atencao("A chave parece curta (a da Garmin tem mais de 128 caracteres).")
    except (gp.Erro, gp.ErroCofre) as e:
        falha(str(e))

    # --- vencimento da chave
    v = configuracao.vencimento(pasta)
    if v is None:
        atencao("Data de vencimento da chave não informada. Veja a data em "
                "connect.garmin.com/app/settings/personalApiToken e rode: "
                "py garmin_painel.py --chave-vence AAAA-MM-DD")
    else:
        data, dias = v
        br = data.strftime("%d/%m/%Y")
        if dias < 0:
            falha(f"A chave venceu em {br}. Crie outra no Garmin Connect.")
        elif dias <= configuracao.AVISAR_DIAS:
            atencao(f"A chave vence em {dias} dia(s) ({br}).")
        else:
            ok(f"A chave vence em {br} (faltam {dias} dias)")

    # --- token guardado
    tok = gp.ler_token_cache()
    if not tok or "|" not in tok:
        ok("Nenhum token guardado no cofre (normal na primeira vez ou fora do Windows)")
    else:
        exp = gp._exp_do_token(tok.split("|", 1)[1])
        resta = None if exp is None else exp - time.time()
        if resta is None:
            atencao("Há um token guardado, mas não consegui ler a validade dele.")
        elif resta <= 0:
            ok("O token guardado venceu; um novo será pedido na próxima execução")
        else:
            ok(f"Token guardado, válido por mais ~{_idade(resta)}")

    # --- conexão e autenticação
    if chave:
        try:
            gp.Cliente(chave).get("/userprofile-service/userprofile/settings")
            ok("Conexão e autenticação com a Garmin funcionando")
        except gp.Erro as e:
            falha(f"Não consegui falar com a Garmin: {e}")

    # --- dados guardados
    caminho = gp.caminho_armazem()
    if not os.path.exists(caminho):
        atencao("Ainda não há dados guardados. Rode a atualização uma vez.")
    else:
        d = armazem.carregar(caminho)
        if not d.get("ultima_busca"):
            atencao("O arquivo de dados guardados está vazio.")
        else:
            idade = time.time() - os.path.getmtime(caminho)
            msg = (f"Dados guardados: {len(d['resumos'])} dias, {len(d['atividades'])} "
                   f"atividades, desde {d['cobertura_ini']}; atualizados há {_idade(idade)}")
            (atencao if idade > 24 * 3600 else ok)(
                msg + (" (mais de 1 dia: a atualização automática pode estar parada)"
                       if idade > 24 * 3600 else ""))
            if d.get("vfc_pendente_ini"):
                atencao("A VFC falhou numa busca anterior e será refeita na próxima.")
    n = len(armazem.listar_backups(caminho))
    (ok if n else atencao)(f"Backups dos dados: {n} cópia(s)" if n else
                           "Ainda não há backup dos dados (o primeiro é feito na próxima atualização)")

    # --- painel e log
    painel = os.path.join(pasta, "painel.html")
    if os.path.exists(painel):
        ok(f"painel.html gerado há {_idade(time.time() - os.path.getmtime(painel))}")
    else:
        atencao("painel.html ainda não existe.")
    log = os.path.join(gp.PASTA, "ultimo_log.txt")
    if os.path.exists(log):
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                linhas = [x.strip() for x in f if x.strip()]
            erros = [x for x in linhas if x.startswith("ERRO")]
            quando = _idade(time.time() - os.path.getmtime(log))
            if erros:
                atencao(f"A última atualização automática (há {quando}) falhou: {erros[-1]}")
            else:
                ok(f"Última atualização automática há {quando}, sem erros")
        except OSError:
            atencao("Não consegui ler o ultimo_log.txt.")

    # --- biblioteca oficial da Garmin para rotas (opcional)
    import rotas
    if rotas.carregar_sdk() is None:
        ok("Biblioteca oficial para rotas (FIT): não instalada (só é necessária para as rotas)")
    else:
        ok(f"Biblioteca oficial para rotas (FIT): garmin-fit-sdk {rotas.versao_sdk()} instalada")
        rg = rotas.carregar_rotas(pasta)
        com = sum(1 for v in rg.values() if "pts" in v)
        ok(f"Rotas guardadas: {com} com trilha, {sum(1 for v in rg.values() if v.get('sem_gps'))} sem GPS, "
           f"{sum(1 for v in rg.values() if v.get('falhou'))} com falha")

    # --- tarefa agendada (Windows)
    if sys.platform == "win32":
        existe = comando_ok(["schtasks", "/Query", "/TN", NOME_TAREFA])
        if existe is None:
            atencao("Não consegui consultar o Agendador de Tarefas.")
        elif existe:
            ok(f"Atualização automática ('{NOME_TAREFA}') configurada")
        else:
            atencao("Atualização automática não está configurada (veja o GUIA.md)")

    print()
    if cont["falha"]:
        print(f"Resultado: {cont['falha']} falha(s) e {cont['atencao']} atenção(ões). "
              "Resolva as FALHAS primeiro.")
        return 1
    print("Resultado: tudo certo." if not cont["atencao"]
          else f"Resultado: funcionando, com {cont['atencao']} ponto(s) de atenção.")
    return 0

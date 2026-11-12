#!/usr/bin/env python3
"""Painel pessoal com dados da Garmin, usando a Personal API oficial.

- Só LÊ dados (requisições GET). A única requisição POST é a que troca a
  chave pessoal por um token temporário (endpoint oficial de token).
- A chave é lida do cofre do sistema (Gerenciador de Credenciais do Windows
  ou Chaves do Mac) na hora de usar. Nunca é impressa nem gravada em arquivo.
- O token (vale 24 h) fica na memória e, no Windows, também no cofre
  (garmin-personal-api-token) para ser reaproveitado. Nunca vai para arquivo.
- Os dados brutos ficam em dados_brutos.json (sem chave/token), só neste
  computador: as próximas execuções buscam só o que é novo.
- Nenhuma biblioteca de terceiros: só a biblioteca padrão do Python.

Uso:
    python garmin_painel.py --teste            # testa com 1 dia (ontem)
    python garmin_painel.py                    # atualiza e gera painel.html
    python garmin_painel.py --so-visual        # redesenha SEM consultar a Garmin
    python garmin_painel.py --dias 60          # período maior (padrão 30)
    python garmin_painel.py --sem-abrir        # não abre o navegador
    python garmin_painel.py --esquecer-token   # apaga o token guardado no cofre
    python garmin_painel.py --diagnostico      # confere tudo e diz o que está errado
    python garmin_painel.py --chave-vence 2027-02-09   # avisa antes da chave vencer
    python garmin_painel.py --meta km-mes=50   # sua meta (veja --ajuda)
    python garmin_painel.py --historico 365    # busca mais histórico (recordes)
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armazem  # noqa: E402
import configuracao  # noqa: E402
import diagnostico  # noqa: E402
import metas  # noqa: E402
from cofre import (ErroCofre, apagar_token_cache, gravar_token_cache,  # noqa: E402
                   ler_chave, ler_token_cache)
from formatos import (MELHORES, SEM_DADO, hms, km, pace,  # noqa: E402
                      pace_de_velocidade, segunda)
from visual import pagina  # noqa: E402

BASE = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
UA = "painel-pessoal/1.0"
PASTA = os.path.dirname(os.path.abspath(__file__))
PAGINA_ATIVIDADES = 20      # respostas grandes podem falhar: páginas pequenas
FOLGA_TOKEN_S = 3600        # só reaproveita token com mais de 1 h de validade


class Erro(Exception):
    """Erro com mensagem segura (nunca contém chave nem token)."""


# -------------------------------------------------------------- cliente ----
def _exp_do_token(token):
    """Validade (epoch) lida do próprio token, ou None. Não mostra nada."""
    try:
        parte = token.split(".")[1]
        parte += "=" * (-len(parte) % 4)
        return float(json.loads(base64.urlsafe_b64decode(parte))["exp"])
    except Exception:
        return None


class Cliente:
    """Fala com a Garmin. Só faz GET nos dados; POST só para o token."""

    def __init__(self, chave):
        self._chave = chave
        self._token = None
        self._id = hashlib.sha256(chave.encode()).hexdigest()[:16]
        self._cache_tentado = False

    def _abrir(self, req):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            dica = {
                400: "pedido inválido",
                401: "chave/token recusado (a chave pode ter expirado ou "
                     "sido apagada)",
                403: "acesso negado",
                404: "não encontrado",
                429: "muitos pedidos seguidos; espere uns minutos",
            }.get(e.code, "erro do servidor" if e.code >= 500 else "erro")
            raise Erro(f"A Garmin respondeu {e.code} ({dica}).") from None
        except urllib.error.URLError as e:
            raise Erro("Sem conexão com a Garmin: "
                       f"{type(e.reason).__name__}.") from None

    def _token_do_cache(self):
        bruto = ler_token_cache()
        if not bruto or "|" not in bruto:
            return None
        cid, tok = bruto.split("|", 1)
        exp = _exp_do_token(tok)
        if cid != self._id or exp is None or exp - time.time() < FOLGA_TOKEN_S:
            return None
        return tok

    def _novo_token(self):
        if not self._cache_tentado:
            self._cache_tentado = True
            self._token = self._token_do_cache()
            if self._token:
                return
        req = urllib.request.Request(
            TOKEN_URL(), data=b"", method="POST",
            headers={"Authorization": "ApiKey " + self._chave,
                     "User-Agent": UA})
        corpo = self._abrir(req).decode("utf-8", "replace").strip()
        token = None
        try:
            dados = json.loads(corpo)
            if isinstance(dados, dict):
                for k in ("access_token", "accessToken", "token"):
                    if isinstance(dados.get(k), str) and dados[k]:
                        token = dados[k]
                        break
                if token is None:
                    raise Erro("Resposta do token em formato inesperado "
                               f"(campos: {sorted(dados)}).")
            elif isinstance(dados, str):
                token = dados
        except json.JSONDecodeError:
            token = corpo or None
        if not token:
            raise Erro("A Garmin não devolveu um token.")
        self._token = token
        exp = _exp_do_token(token)
        if exp and exp - time.time() > FOLGA_TOKEN_S:
            gravar_token_cache(f"{self._id}|{token}")

    def get(self, caminho, params=None):
        """GET autenticado. Devolve o JSON já convertido."""
        url = BASE + caminho
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for tentativa in range(4):
            if self._token is None:
                self._novo_token()
            req = urllib.request.Request(
                url, method="GET",
                headers={"Authorization": "Bearer " + self._token,
                         "Accept": "application/json", "User-Agent": UA})
            try:
                corpo = self._abrir(req)
                return json.loads(corpo) if corpo.strip() else None
            except Erro as e:
                msg = str(e)
                if "401" in msg and tentativa == 0:
                    self._token = None      # token vencido/revogado: renova
                    self._cache_tentado = True
                    apagar_token_cache()
                    continue
                if ("429" in msg or "respondeu 5" in msg) and tentativa < 3:
                    time.sleep(3 * (tentativa + 1))
                    continue
                raise
        raise Erro("Não consegui concluir o pedido.")


def TOKEN_URL():
    return BASE + TOKEN_PATH


# ---------------------------------------------------------------- dados ----
def _lista(resposta):
    if resposta is None:
        return []
    if isinstance(resposta, list):
        return resposta
    if isinstance(resposta, dict):
        for k in ("data", "dailySleepDTOList", "items"):
            if isinstance(resposta.get(k), list):
                return resposta[k]
    return []


def blocos(ini, fim, passo):
    """Divide [ini, fim] em blocos de até `passo` dias."""
    atual = ini
    while atual <= fim:
        topo = min(atual + dt.timedelta(days=passo - 1), fim)
        yield atual, topo
        atual = topo + dt.timedelta(days=1)


def buscar_resumos(c, ini, fim):
    out = []
    for a, b in blocos(ini, fim, 7):
        out += _lista(c.get("/usersummary-service/v2/dailysummaries",
                            {"startDate": a.isoformat(),
                             "endDate": b.isoformat()}))
        time.sleep(0.3)
    return out


def buscar_sono(c, ini, fim):
    out = []
    for a, b in blocos(ini, fim, 7):
        out += _lista(c.get("/sleep-service/sleep/dailySleepSummariesByDate",
                            {"startDate": a.isoformat(),
                             "endDate": b.isoformat()}))
        time.sleep(0.3)
    return out


def buscar_vfc(c, ini, fim):
    """VFC (média da noite) por dia. Devolve {data: valor}."""
    out = {}
    for a, b in blocos(ini, fim, 7):
        r = c.get(f"/hrv-service/hrv/daily/{a.isoformat()}/{b.isoformat()}")
        for item in (g(r, "hrvSummaries") or []):
            v = g(item, "lastNightAvg")
            if g(item, "calendarDate") and isinstance(v, (int, float)) and v > 0:
                out[item["calendarDate"]] = v
        time.sleep(0.3)
    return out


def buscar_peso(c, ini, fim):
    """Peso (kg) por dia: a última medição de cada dia. Devolve {data: kg}.
    Sem balança conectada a lista vem vazia. Valores acima de 300 são tratados
    como gramas (alguns serviços da Garmin respondem em gramas)."""
    out = {}
    for a, b in blocos(ini, fim, 28):
        r = c.get(f"/weight-service/weight/all/{a.isoformat()}/{b.isoformat()}")
        itens = sorted((x for x in _lista(r) if isinstance(x, dict)),
                       key=lambda x: str(g(x, "timestampGMT") or ""))
        for item in itens:                    # a última do dia sobrescreve
            data, w = g(item, "calendarDate"), g(item, "weight")
            if data and isinstance(w, (int, float)) and w > 0:
                out[data] = round(w / 1000 if w > 300 else w, 2)
        time.sleep(0.3)
    return out


def buscar_atividades(c, ini, fim):
    """Lê página a página até vir uma página vazia (uma página curta não
    indica o fim: a Garmin pode devolver menos que o pedido)."""
    out, inicio = [], 0
    for _ in range(200):
        lote = _lista(c.get("/activitylist-service/activities/search/activities",
                            {"startDate": ini.isoformat(),
                             "endDate": fim.isoformat(),
                             "start": inicio, "limit": PAGINA_ATIVIDADES}))
        if not lote:
            break
        out += lote
        inicio += len(lote)
        time.sleep(0.3)
    return out


def g(d, *chaves):
    """Acesso seguro a campos aninhados; None se não existir."""
    for k in chaves:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _pos(v):
    """Garmin às vezes usa valores negativos para 'sem medida'."""
    return v if isinstance(v, (int, float)) and v >= 0 else None


def _maior0(v):
    """Para medidas em que 0 significa que o relógio não mediu."""
    return v if isinstance(v, (int, float)) and v > 0 else None


def montar_dias(resumos, sonos, vfc=None, peso=None):
    """Junta resumo diário e sono por data. Todo valor vem da Garmin."""
    dias = {}
    for r in resumos:
        data = g(r, "calendarDate")
        if not data:
            continue
        mod, vig = _pos(g(r, "intensityMinutes", "moderate")), \
            _pos(g(r, "intensityMinutes", "vigorous"))
        dias[data] = {
            "data": data,
            "passos": _maior0(g(r, "movement", "steps", "value")),
            "meta_passos": _maior0(g(r, "movement", "steps", "goal")),
            "fc_repouso": _maior0(g(r, "heartRate", "restingValue")),
            "fc_min": _pos(g(r, "heartRate", "minValue")),
            "fc_max": _pos(g(r, "heartRate", "maxValue")),
            "estresse": _pos(g(r, "stress", "avgLevel")),
            "bb_min": _pos(g(r, "bodyBattery", "minValue")),
            "bb_max": _pos(g(r, "bodyBattery", "maxValue")),
            "intensidade": None if mod is None and vig is None
            else (mod or 0) + (vig or 0),
            "calorias": _maior0(g(r, "calories", "burnedTotal")),
            "respiracao": _pos(g(r, "respiration", "avgValue")),
            "spo2": _pos(g(r, "pulseOx", "avgValue")),
            "andares": _pos(g(r, "movement", "floorsAscended", "value")),
            "hidrat_ml": _maior0(g(r, "hydration", "consumedInFractionalMl")),
            "meta_hidrat_ml": _maior0(g(r, "hydration", "goalInFractionalMl")
                                      or g(r, "hydration", "goalInMl")),
            "sono_s": None, "sono_prof_s": None, "sono_leve_s": None,
            "sono_rem_s": None,
            "vfc": None, "peso": None,
        }
    for s in sonos:
        if isinstance(g(s, "dailySleepDTO"), dict):   # caso venha embrulhado
            s = s["dailySleepDTO"]
        data = g(s, "calendarDate")
        if not data:
            continue
        d = dias.setdefault(data, {"data": data})
        seg = g(s, "sleepTimeSeconds")
        d["sono_s"] = seg if isinstance(seg, (int, float)) and seg > 0 else None
        if d["sono_s"]:
            d["sono_prof_s"] = _pos(g(s, "deepSleepSeconds"))
            d["sono_leve_s"] = _pos(g(s, "lightSleepSeconds"))
            # relógio sem sensor de REM: não há medida, em vez de zero
            d["sono_rem_s"] = (None if g(s, "deviceRemCapable") is False
                               else _pos(g(s, "remSleepSeconds")))
    for data, v in (vfc or {}).items():
        dias.setdefault(data, {"data": data})["vfc"] = v
    for data, v in (peso or {}).items():
        dias.setdefault(data, {"data": data})["peso"] = v
    return [dias[k] for k in sorted(dias)]


def montar_atividades(brutas):
    out = []
    for a in brutas:
        zonas = [_pos(g(a, f"hrTimeInZone_{z}")) for z in range(1, 6)]
        out.append({
            "id": g(a, "activityId"),
            "data": (g(a, "startTimeLocal") or "")[:10] or None,
            "hora": (g(a, "startTimeLocal") or "")[11:16] or None,
            "tipo": g(a, "activityType", "typeKey"),
            "nome": g(a, "activityName"),
            "dist_m": g(a, "distance"),
            "dur_s": g(a, "duration"),
            "vel_ms": g(a, "averageSpeed"),
            "fc_media": _maior0(g(a, "averageHR")),
            "cad": _maior0(g(a, "averageRunningCadenceInStepsPerMinute")),
            "elev_m": _pos(g(a, "elevationGain")),
            "vo2": _maior0(g(a, "vO2MaxValue")),
            "zonas": zonas if any(z for z in zonas) else None,
            "melhores": {m: _maior0(g(a, f"fastestSplit_{m}")) for m, _ in MELHORES},
        })
    out.sort(key=lambda x: (x["data"] or "", x["hora"] or ""), reverse=True)
    return out


# ----------------------------------------------------------------- modos ---
def modo_teste(cli, dia):
    print(f"Teste com 1 dia: {dia.isoformat()}")
    resumos = buscar_resumos(cli, dia, dia)
    sonos = buscar_sono(cli, dia, dia)
    ativ = buscar_atividades(cli, dia, dia)
    d = montar_dias(resumos, sonos)
    print(f"- Resumo diário: {len(resumos)} registro(s)")
    print(f"- Sono: {len(sonos)} registro(s)")
    print(f"- Atividades: {len(ativ)}")
    for linha in d:
        for k, v in linha.items():
            print(f"    {k}: {SEM_DADO if v is None else v}")
    for a in montar_atividades(ativ):
        print(f"    atividade {a['data']} {a['hora']} {a['tipo']}: "
              f"{km(a['dist_m'])}, {hms(a['dur_s'])}, "
              f"{pace(pace_de_velocidade(a['vel_ms']))}")
    print("Teste concluído. Nenhuma chave nem token foi mostrado ou salvo.")


PASTA_DADOS = None   # definida por --pasta-dados ou GARMIN_PAINEL_PASTA_DADOS


def pasta_dados():
    """Onde ficam painel.html e dados_brutos.json (padrão: pasta do programa)."""
    p = PASTA_DADOS or os.environ.get("GARMIN_PAINEL_PASTA_DADOS") or PASTA
    os.makedirs(p, exist_ok=True)
    return p


def caminho_armazem():
    return os.path.join(pasta_dados(), "dados_brutos.json")


def atualizar_armazem(cli, dados, hoje, ini):
    """Busca na Garmin só o que falta e guarda. Devolve a lista de avisos."""
    avisos = []
    for jan in armazem.planejar(dados, hoje, ini):
        print(f"Buscando de {jan[0]} a {jan[1]} ...")
        resumos = buscar_resumos(cli, *jan)
        sonos = buscar_sono(cli, *jan)
        try:
            vfc = buscar_vfc(cli, *jan)
            armazem.marcar_vfc(dados, jan, True)
        except Erro as e:
            vfc = {}
            armazem.marcar_vfc(dados, jan, False)     # tenta de novo na próxima vez
            avisos.append(f"VFC não pôde ser lida ({e}); será tentada de novo "
                          "na próxima atualização")
        try:
            peso = buscar_peso(cli, *jan)
            armazem.marcar_pendente(dados, "peso", jan, True)
        except Erro as e:
            peso = {}
            if "403" in str(e) or "404" in str(e):
                pass          # sem acesso/sem esse recurso: tratado como "sem dado"
            else:
                armazem.marcar_pendente(dados, "peso", jan, False)
                avisos.append(f"Peso não pôde ser lido ({e}); será tentado de novo "
                              "na próxima atualização")
        ativ = buscar_atividades(cli, *jan)
        armazem.mesclar(dados, jan, resumos, sonos, vfc, ativ, peso)
        print(f"- resumos: {len(resumos)} - sono: {len(sonos)} - "
              f"VFC: {len(vfc)} - peso: {len(peso)} - atividades: {len(ativ)}")
    armazem.fechar(dados, hoje, ini)
    try:
        armazem.backup_diario(caminho_armazem())   # cópia do arquivo ANTES de mudar
    except OSError:
        avisos.append("Não consegui fazer a cópia de segurança dos dados guardados")
    try:
        armazem.salvar(caminho_armazem(), dados)
    except OSError as e:
        avisos.append("Não consegui guardar os dados em dados_brutos.json "
                      f"({type(e).__name__}); o painel foi gerado mesmo assim, "
                      "mas a próxima atualização buscará tudo de novo")
    return avisos


def gerar(dados, hoje, ini, agora, avisos, abrir):
    resumos, sonos, vfc, brutas, peso = armazem.recorte(dados, ini, hoje)
    ativ = montar_atividades(brutas)
    historico = montar_atividades(armazem.todas_atividades(dados))
    pasta = pasta_dados()
    alerta = configuracao.alerta(pasta)
    venc = configuracao.vencimento(pasta)
    pag, omitidos = pagina(montar_dias(resumos, sonos, vfc, peso), ativ, ini, hoje,
                           agora, avisos, [alerta] if alerta else None,
                           venc[0] if venc else None,
                           historico=historico, metas=metas.progresso(pasta, historico, hoje),
                           cobertura_ini=dados.get("cobertura_ini"))
    caminho = os.path.join(pasta, "painel.html")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(pag)
    print(f"Painel gerado: {caminho}")
    for nome in omitidos:
        print(f"AVISO: '{nome}' não aparece: sem dados no período "
              "(o relógio não mediu ou a Garmin não enviou).")
    for a in avisos:
        print(f"AVISO: {a}")
    if alerta:
        print(f"AVISO: {alerta}")
    if abrir:
        webbrowser.open("file:///" + caminho.replace("\\", "/"))


def periodo(dias):
    hoje = dt.date.today()
    # começa na segunda-feira para a primeira semana ficar completa, e sempre
    # cobre o mês corrente inteiro (para a meta mensal)
    ini = segunda(hoje - dt.timedelta(days=max(dias, 14) - 1))
    return hoje, min(ini, segunda(hoje.replace(day=1)))


def main(argv=None):
    p = argparse.ArgumentParser(description="Painel pessoal Garmin")
    p.add_argument("--teste", action="store_true",
                   help="testa com 1 dia e mostra os números no terminal")
    p.add_argument("--data", help="dia do teste (AAAA-MM-DD); padrão: ontem")
    p.add_argument("--dias", type=int, default=30,
                   help="período do painel em dias (padrão 30)")
    p.add_argument("--sem-abrir", action="store_true",
                   help="não abre o painel no navegador")
    p.add_argument("--so-visual", action="store_true",
                   help="redesenha o painel com os dados já guardados, "
                        "sem consultar a Garmin")
    p.add_argument("--pasta-dados", metavar="PASTA",
                   help="onde guardar painel.html e dados_brutos.json (útil para "
                        "fora de pastas sincronizadas, como o OneDrive)")
    p.add_argument("--diagnostico", action="store_true",
                   help="confere chave, token, conexão, dados e agendamento")
    p.add_argument("--chave-vence", metavar="DATA",
                   help="data em que a chave vence (AAAA-MM-DD), para o painel avisar antes")
    p.add_argument("--meta", action="append", metavar="NOME=VALOR",
                   help="define uma meta sua: " + ", ".join(metas.METAS) +
                        " (ex.: --meta km-mes=50)")
    p.add_argument("--remover-meta", metavar="NOME", help="apaga uma meta")
    p.add_argument("--historico", type=int, metavar="DIAS",
                   help="busca também o histórico dos últimos DIAS dias (para os "
                        "recordes); demora na primeira vez")
    p.add_argument("--esquecer-token", action="store_true",
                   help="apaga o token guardado no cofre do Windows")
    a = p.parse_args(argv)
    global PASTA_DADOS
    PASTA_DADOS = a.pasta_dados
    try:
        if a.diagnostico:
            return diagnostico.executar()
        if a.chave_vence:
            try:
                data = configuracao.definir_vencimento(pasta_dados(), a.chave_vence)
            except ValueError as e:
                raise Erro(str(e)) from None
            dias = (data - dt.date.today()).days
            print(f"Vencimento da chave registrado: {data.strftime('%d/%m/%Y')} "
                  f"({'faltam ' + str(dias) + ' dias' if dias >= 0 else 'já venceu'}).")
            return 0
        if a.meta or a.remover_meta:
            for texto in (a.meta or []):
                try:
                    nome, v = metas.definir(pasta_dados(), texto)
                except ValueError as e:
                    raise Erro(str(e)) from None
                print(f"Meta definida: {metas.METAS[nome][0]} = {v:g} {metas.METAS[nome][1]}")
            if a.remover_meta:
                try:
                    metas.remover(pasta_dados(), a.remover_meta)
                except ValueError as e:
                    raise Erro(str(e)) from None
                print(f"Meta removida: {a.remover_meta}")
            return 0
        if a.esquecer_token:
            apagar_token_cache()
            print("Token guardado apagado do cofre (se existia). "
                  "A chave não foi tocada.")
            return 0
        dias = max(1, min(a.dias, 365))
        if a.so_visual:
            hoje, ini = periodo(dias)
            dados = armazem.carregar(caminho_armazem())
            if not dados.get("ultima_busca"):
                raise Erro("Ainda não há dados guardados. Rode uma vez sem "
                           "--so-visual para buscar na Garmin.")
            quando = dt.datetime.fromisoformat(dados["atualizado_em"])
            avisos = ["Visual redesenhado sem consultar a Garmin: dados de "
                      f"{quando.strftime('%d/%m/%Y %H:%M')}."]
            cob = dt.date.fromisoformat(dados["cobertura_ini"])
            if ini < cob:     # não mostra como "sem dado" o que nunca foi buscado
                ini = cob
                avisos.append(f"Os dados guardados começam em {cob.strftime('%d/%m/%Y')}; "
                              "para um período maior, atualize sem --so-visual.")
            gerar(dados, hoje, ini, quando, avisos, not a.sem_abrir)
            return 0
        cli = Cliente(ler_chave())
        if a.teste:
            dia = (dt.date.fromisoformat(a.data) if a.data
                   else dt.date.today() - dt.timedelta(days=1))
            modo_teste(cli, dia)
        else:
            hoje, ini = periodo(dias)
            dados = armazem.carregar(caminho_armazem())
            busca_ini = ini
            if a.historico:
                busca_ini = min(ini, hoje - dt.timedelta(days=max(1, min(a.historico, 3650)) - 1))
            avisos = atualizar_armazem(cli, dados, hoje, busca_ini)
            gerar(dados, hoje, ini, dt.datetime.now(), avisos, not a.sem_abrir)
        return 0
    except (Erro, ErroCofre) as e:
        print(f"ERRO: {e}")
        return 1
    except Exception as e:  # nunca mostra detalhes que possam ter segredos
        print(f"ERRO inesperado: {type(e).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

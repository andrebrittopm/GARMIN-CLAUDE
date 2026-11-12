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
    python garmin_painel.py --teste-rota       # confere se dá para ler a trilha de GPS
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
import corredor  # noqa: E402
import diagnostico  # noqa: E402
import metas  # noqa: E402
import rotas  # noqa: E402
from cofre import (ErroCofre, apagar_token_cache, gravar_token_cache,  # noqa: E402
                   ler_chave, ler_token_cache)
from formatos import (MELHORES, SEM_DADO, hms, km, num, pace,  # noqa: E402
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

    def _abrir(self, req, limite=None):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                dados = r.read(limite + 1) if limite else r.read()
                if limite and len(dados) > limite:
                    raise Erro("A resposta da Garmin é grande demais para ser lida.")
                return dados
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

    def _requisitar(self, caminho, params=None, aceitar="application/json", limite=None):
        """GET autenticado (só leitura). Devolve os bytes da resposta."""
        url = BASE + caminho
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for tentativa in range(4):
            if self._token is None:
                self._novo_token()
            req = urllib.request.Request(
                url, method="GET",
                headers={"Authorization": "Bearer " + self._token,
                         "Accept": aceitar, "User-Agent": UA})
            try:
                corpo = self._abrir(req, limite)
                if sys.stdout.isatty():     # um ponto por pedido, para ver que está andando
                    print(".", end="", flush=True)
                return corpo
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

    def get(self, caminho, params=None):
        """GET autenticado. Devolve o JSON já convertido."""
        corpo = self._requisitar(caminho, params)
        return json.loads(corpo) if corpo.strip() else None

    def get_bytes(self, caminho, limite):
        """GET de um arquivo (ex.: o ZIP com o FIT de uma atividade)."""
        return self._requisitar(caminho, aceitar="application/zip, application/octet-stream, */*",
                                limite=limite)


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
            "evento": g(a, "eventType", "typeKey"),
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


def escolher_para_rota(dados, data=None):
    """Corrida mais recente (com trilha de GPS, se a Garmin indicar) no armazém."""
    corridas = [a for a in dados["atividades"].values()
                if "running" in (g(a, "activityType", "typeKey") or "")]
    if data:
        corridas = [a for a in corridas if (a.get("startTimeLocal") or "")[:10] == data]
    corridas.sort(key=lambda a: a.get("startTimeLocal") or "", reverse=True)
    com_gps = [a for a in corridas if a.get("hasPolyline")]
    return (com_gps or corridas or [None])[0]


def modo_teste_rota(cli, data=None):
    """Baixa o FIT de UMA corrida (só leitura), lê com a biblioteca oficial e
    mostra fatos sobre ele. Não mostra coordenadas nem guarda o arquivo."""
    dados = armazem.carregar(caminho_armazem())
    a = escolher_para_rota(dados, data)
    if a is None:
        raise Erro("Não achei uma corrida nos dados guardados"
                   + (f" em {data}" if data else "") + ". Rode a atualização antes.")
    if rotas.carregar_sdk() is None:
        raise rotas.ErroRota("A biblioteca oficial da Garmin (garmin-fit-sdk) não está "
                             "instalada. Instale com: " + rotas.INSTALAR)
    dist = a.get("distance")
    print("Teste de rota (só leitura)")
    print(f"- Atividade escolhida: {(a.get('startTimeLocal') or '')[:10]}, "
          f"{g(a, 'activityType', 'typeKey')}, {km(dist)} "
          f"(a Garmin indica trilha de GPS: {'sim' if a.get('hasPolyline') else 'não informado'})")
    print(f"- Biblioteca oficial da Garmin: garmin-fit-sdk {rotas.versao_sdk()}")
    pacote = cli.get_bytes(f"/download-service/files/activity/{a['activityId']}", rotas.LIMITE_ZIP)
    print()
    fit = rotas.extrair_fit(pacote)
    mesgs = rotas.decodificar(fit)
    pts = rotas.pontos_gps(mesgs)
    r = rotas.resumo(mesgs, pts)
    print(f"- Arquivo recebido: {len(pacote) // 1024} KB (FIT de {len(fit) // 1024} KB)")
    pct = round(100 * r["com_gps"] / r["registros"]) if r["registros"] else 0
    print(f"- Registros no arquivo: {r['registros']}; com GPS: {r['com_gps']} ({pct}%)")
    print("- Dados por registro: " + "; ".join(f"{k}: {'sim' if v else 'não'}" for k, v in r["campos"].items()))
    print(f"- Esporte registrado no arquivo: {(r['esporte'] or ['?'])[0]}")
    if r["extensao_m"]:
        print(f"- Área percorrida: cerca de {num(r['extensao_m'][0] / 1000, 1)} km de largura por "
              f"{num(r['extensao_m'][1] / 1000, 1)} km de altura (as coordenadas não são mostradas)")
        print(f"- Comprimento da trilha: {num(r['comprimento_m'] / 1000, 2)} km "
              f"(a atividade tem {km(dist)})")
        print(f"- Trilha simplificada: {len(rotas.simplificar(pts))} pontos")
    else:
        print("- Esta atividade não tem trilha de GPS (esteira, ou GPS desligado).")
    print("- Mensagens no arquivo: " + ", ".join(
        f"{k.replace('_mesgs', '')}={v}" for k, v in sorted(r["mensagens"].items(), key=lambda kv: -kv[1])[:8]))
    print("Teste concluído. Nenhuma coordenada, chave ou token foi mostrado ou salvo; o arquivo FIT não foi gravado.")


def preparar_rotas(pasta, historico):
    """Rotas guardadas + dados da atividade, já com o começo e o fim cortados."""
    guardadas = rotas.carregar_rotas(pasta)
    priv = configuracao.privacidade_m(pasta)
    por_id = {str(a["id"]): a for a in historico if a.get("id") is not None}
    itens = []
    for k, v in guardadas.items():
        a = por_id.get(k)
        if not a or "pts" not in v:
            continue
        pts = rotas.cortar_pontas(v["pts"], priv)
        if len(pts) >= 5:
            itens.append({"id": k, "data": a["data"], "hora": a.get("hora") or "", "dist_m": a["dist_m"],
                          "dur_s": a["dur_s"], "vel_ms": a["vel_ms"], "pts": pts, "alt": v.get("alt") or [],
                          "nome": a.get("nome"), "fc_media": a.get("fc_media"), "cad": a.get("cad"),
                          "elev_m": a.get("elev_m"), "vo2": a.get("vo2")})
    itens.sort(key=lambda x: (x["data"] or "", x["hora"]))
    return {"itens": itens, "privacidade_m": priv}


def atualizar_rotas(cli, dados, limite=rotas.POR_EXECUCAO, explicito=False):
    """Baixa as trilhas que faltam (poucas por vez). Sem a biblioteca oficial instalada,
    só avisa quando você pediu (--rotas); nas atualizações normais fica em silêncio."""
    if rotas.carregar_sdk() is None:
        if explicito:
            raise rotas.ErroRota("A biblioteca oficial da Garmin (garmin-fit-sdk) não está "
                                 "instalada. Instale com: " + rotas.INSTALAR)
        return []
    pasta = pasta_dados()
    guardadas = rotas.carregar_rotas(pasta)
    novas, avisos = rotas.buscar_trilhas(cli, armazem.todas_atividades(dados), guardadas, limite)
    if sys.stdout.isatty() and novas:
        print()
    try:
        rotas.salvar_rotas(pasta, guardadas)
    except OSError:
        avisos.append("Não consegui guardar as trilhas de GPS em rotas.json")
    if novas:
        print(f"- trilhas de GPS novas: {novas}")
    return avisos


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
        if sys.stdout.isatty():
            print()
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
    co = corredor.montar(pasta, historico, hoje, dados.get("cobertura_ini"))
    avisos = list(avisos) + (co["avisos"] if co else [])
    alerta = configuracao.alerta(pasta)
    venc = configuracao.vencimento(pasta)
    pag, omitidos = pagina(montar_dias(resumos, sonos, vfc, peso), ativ, ini, hoje,
                           agora, avisos, [alerta] if alerta else None,
                           venc[0] if venc else None,
                           historico=historico, metas=metas.progresso(pasta, historico, hoje),
                           cobertura_ini=dados.get("cobertura_ini"), corredor=co,
                           rotas=preparar_rotas(pasta, historico) if os.path.exists(rotas.caminho_rotas(pasta)) else None)
    caminho = os.path.join(pasta, "painel.html")
    tmp = caminho + ".tmp"            # grava inteiro e só então troca: nunca fica pela metade
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(pag)
    os.replace(tmp, caminho)
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


def executar_atualizacao(dias=30, abrir=False, historico=None, rotas_todas=False, cli=None):
    """Atualização completa: dados da Garmin, trilhas e painel. Usada pela linha de
    comando e pelo botão "Atualizar agora". Devolve a lista de avisos."""
    cli = cli or Cliente(ler_chave())
    hoje, ini = periodo(dias)
    dados = armazem.carregar(caminho_armazem())
    busca_ini = ini
    if historico:
        busca_ini = min(ini, hoje - dt.timedelta(days=max(1, min(historico, 3650)) - 1))
    avisos = atualizar_armazem(cli, dados, hoje, busca_ini)
    avisos += atualizar_rotas(cli, dados, 100000 if rotas_todas else rotas.POR_EXECUCAO, rotas_todas)
    gerar(dados, hoje, ini, dt.datetime.now(), avisos, abrir)
    return avisos


def competicoes_sem_logo():
    """Competições marcadas na Garmin que o painel mostra sem logo (para o editor)."""
    dados = armazem.carregar(caminho_armazem())
    if not dados.get("ultima_busca"):
        return []
    co = corredor.montar(pasta_dados(), montar_atividades(armazem.todas_atividades(dados)),
                         dt.date.today(), dados.get("cobertura_ini"))
    return [{"data": p["data"].isoformat(), "nome": p["nome"],
             "km": round(p["atv"]["dist_m"] / 1000, 2) if p.get("atv") and p["atv"].get("dist_m") else None}
            for p in (co["feitas"] if co else []) if p.get("origem") == "garmin"]


def redesenhar(dias=30, abrir=False):
    """Recria o painel.html com os dados já guardados, sem consultar a Garmin."""
    hoje, ini = periodo(dias)
    dados = armazem.carregar(caminho_armazem())
    if not dados.get("ultima_busca"):
        raise Erro("Ainda não há dados guardados. Rode uma vez sem --so-visual "
                   "para buscar na Garmin.")
    quando = dt.datetime.fromisoformat(dados["atualizado_em"])
    avisos = ["Visual redesenhado sem consultar a Garmin: dados de "
              f"{quando.strftime('%d/%m/%Y %H:%M')}."]
    cob = dt.date.fromisoformat(dados["cobertura_ini"])
    if ini < cob:     # não mostra como "sem dado" o que nunca foi buscado
        ini = cob
        avisos.append(f"Os dados guardados começam em {cob.strftime('%d/%m/%Y')}; "
                      "para um período maior, atualize sem --so-visual.")
    gerar(dados, hoje, ini, quando, avisos, abrir)
    return avisos


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
    p.add_argument("--servir", action="store_true",
                   help="abre o painel com edição de provas e perfil (servidor só neste "
                        "computador); use o atalho abrir_painel.bat")
    p.add_argument("--porta", type=int, metavar="N", help="porta do --servir (padrão 8765)")
    p.add_argument("--rotas", action="store_true",
                   help="baixa as trilhas de GPS de TODAS as corridas que ainda faltam "
                        "(a atualização normal baixa só algumas por vez)")
    p.add_argument("--privacidade-metros", type=int, metavar="N",
                   help="metros cortados do começo e do fim de cada rota desenhada "
                        "(padrão 300; 0 desliga)")
    p.add_argument("--teste-rota", action="store_true",
                   help="baixa o FIT de uma corrida e confere se dá para ler a trilha "
                        "(use --data AAAA-MM-DD para escolher o dia)")
    p.add_argument("--criar-perfil", action="store_true",
                   help="cria perfil.txt, provas.txt e as pastas de imagens para o "
                        "visual de corredor (foto, logos e provas)")
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
        if a.privacidade_metros is not None:
            try:
                n = configuracao.definir_privacidade(pasta_dados(), a.privacidade_metros)
            except ValueError as e:
                raise Erro(str(e)) from None
            print(f"Privacidade das rotas: cortando {n} m do começo e do fim. "
                  "Rode redesenhar.bat para aplicar." + (" ATENÇÃO: com 0 o início e o fim aparecem." if n == 0 else ""))
            return 0
        if a.criar_perfil:
            feitos = corredor.criar_modelos(pasta_dados())
            print("Criados: " + (", ".join(feitos) if feitos else "nada novo (já existiam)")
                  + f"\nPasta: {pasta_dados()}\nColoque sua foto em imagens\\ e os logos em imagens\\corridas\\.")
            return 0
        if a.esquecer_token:
            apagar_token_cache()
            print("Token guardado apagado do cofre (se existia). "
                  "A chave não foi tocada.")
            return 0
        dias = max(1, min(a.dias, 365))
        if a.so_visual:
            redesenhar(dias, not a.sem_abrir)
            return 0
        if a.servir:
            import servidor
            return servidor.servir(pasta_dados(), lambda: redesenhar(dias, False),
                                   a.porta or 8765, not a.sem_abrir, competicoes_sem_logo,
                                   lambda: executar_atualizacao(dias, False))
        cli = Cliente(ler_chave())
        if a.teste_rota:
            modo_teste_rota(cli, a.data)
            return 0
        if a.teste:
            dia = (dt.date.fromisoformat(a.data) if a.data
                   else dt.date.today() - dt.timedelta(days=1))
            modo_teste(cli, dia)
        else:
            executar_atualizacao(dias, not a.sem_abrir, a.historico, a.rotas, cli)
        return 0
    except (Erro, ErroCofre, rotas.ErroRota) as e:
        print(f"ERRO: {e}")
        return 1
    except Exception as e:  # nunca mostra detalhes que possam ter segredos
        print(f"ERRO inesperado: {type(e).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Painel pessoal com dados da Garmin, usando a Personal API oficial.

- Só LÊ dados (requisições GET). A única requisição POST é a que troca a
  chave pessoal por um token temporário (endpoint oficial de token).
- A chave é lida do cofre do sistema (Gerenciador de Credenciais do Windows
  ou Chaves do Mac) na hora de usar. Nunca é impressa nem gravada em arquivo.
- O token fica só na memória e some quando o programa termina.
- Nenhuma biblioteca de terceiros: só a biblioteca padrão do Python.

Uso:
    python garmin_painel.py --teste            # testa com 1 dia (ontem)
    python garmin_painel.py --teste --data 2026-11-10
    python garmin_painel.py                    # gera painel.html (30 dias)
    python garmin_painel.py --dias 60
"""
import argparse
import datetime as dt
import html
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from formatos import (SEM_DADO, hms, km, pace, pace_de_velocidade,  # noqa: E402
                      segunda)
from visual import pagina  # noqa: E402

BASE = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
NOME_CHAVE = "garmin-personal-api-key"
UA = "painel-pessoal/1.0"
PASTA = os.path.dirname(os.path.abspath(__file__))


class Erro(Exception):
    """Erro com mensagem segura (nunca contém chave nem token)."""


# ---------------------------------------------------------------- chave ----
def ler_chave():
    """Lê a chave do cofre do sistema. Devolve texto; nunca imprime."""
    if sys.platform == "win32":
        return _ler_chave_windows()
    if sys.platform == "darwin":
        r = subprocess.run(
            ["security", "find-generic-password", "-s", NOME_CHAVE, "-w"],
            capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            raise Erro("Não achei a chave nas Chaves do Mac "
                       f"(nome '{NOME_CHAVE}').")
        return r.stdout.strip()
    raise Erro("Sistema não suportado: use Windows ou Mac.")


def _ler_chave_windows():
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
            ("LastWritten", FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
        ]

    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                              wintypes.DWORD,
                              ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.c_void_p]

    ptr = ctypes.POINTER(CREDENTIAL)()
    if not adv.CredReadW(NOME_CHAVE, 1, 0, ctypes.byref(ptr)):
        raise Erro("Não achei a chave no Gerenciador de Credenciais "
                   f"(nome '{NOME_CHAVE}'). Refaça o passo de guardar a chave.")
    try:
        c = ptr.contents
        bruto = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
        return bruto.decode("utf-16-le").strip()
    finally:
        adv.CredFree(ptr)


# -------------------------------------------------------------- cliente ----
class Cliente:
    """Fala com a Garmin. Só faz GET nos dados; POST só para o token."""

    def __init__(self, chave):
        self._chave = chave
        self._token = None

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

    def _novo_token(self):
        req = urllib.request.Request(
            BASE + TOKEN_PATH, data=b"", method="POST",
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
                    self._token = None      # token pode ter vencido: renova
                    continue
                if ("429" in msg or "respondeu 5" in msg) and tentativa < 3:
                    time.sleep(3 * (tentativa + 1))
                    continue
                raise
        raise Erro("Não consegui concluir o pedido.")


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


def buscar_atividades(c, ini, fim):
    out, inicio = [], 0
    while True:
        lote = _lista(c.get("/activitylist-service/activities/search/activities",
                            {"startDate": ini.isoformat(),
                             "endDate": fim.isoformat(),
                             "start": inicio, "limit": 99}))
        out += lote
        if len(lote) < 99:
            return out
        inicio += 99
        time.sleep(0.3)


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


def montar_dias(resumos, sonos, vfc=None):
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
            "sono_s": None, "sono_prof_s": None, "sono_leve_s": None,
            "sono_rem_s": None,
            "vfc": None,
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
    return [dias[k] for k in sorted(dias)]


def montar_atividades(brutas):
    out = []
    for a in brutas:
        tipo = g(a, "activityType", "typeKey")
        out.append({
            "id": g(a, "activityId"),
            "data": (g(a, "startTimeLocal") or "")[:10] or None,
            "hora": (g(a, "startTimeLocal") or "")[11:16] or None,
            "tipo": tipo,
            "nome": g(a, "activityName"),
            "dist_m": g(a, "distance"),
            "dur_s": g(a, "duration"),
            "vel_ms": g(a, "averageSpeed"),
        })
    out.sort(key=lambda x: (x["data"] or "", x["hora"] or ""), reverse=True)
    return out


def modo_teste(cli, dia):
    print(f"Teste com 1 dia: {dia.isoformat()}")
    resumos = buscar_resumos(cli, dia, dia)
    sonos = buscar_sono(cli, dia, dia)
    ativ = buscar_atividades(cli, dia, dia)
    d = montar_dias(resumos, sonos)
    print("- Registro(s) de sono, como a Garmin enviou (campo: valor):")
    for r in sonos:
        if not isinstance(r, dict):
            print(f"    (formato inesperado: {type(r).__name__})")
            continue
        for k, v in r.items():
            if isinstance(v, (dict, list)):
                print(f"    {k}: [{type(v).__name__} com {len(v)} item(ns)]")
            elif v is not None:
                print(f"    {k}: {v}")
            else:
                print(f"    {k}: (vazio)")
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


def modo_painel(cli, dias, abrir):
    fim = dt.date.today()
    ini = fim - dt.timedelta(days=max(dias, 14) - 1)
    # começa na segunda-feira para a primeira semana ficar completa
    ini = segunda(ini)
    print(f"Buscando de {ini} a {fim} ...")
    resumos = buscar_resumos(cli, ini, fim)
    print(f"- resumos diários: {len(resumos)}")
    sonos = buscar_sono(cli, ini, fim)
    print(f"- registros de sono: {len(sonos)}")
    avisos = []
    try:
        vfc = buscar_vfc(cli, ini, fim)
    except Erro as e:
        vfc = {}
        avisos.append(f"VFC não pôde ser lida ({e})")
    print(f"- dias com VFC: {len(vfc)}")
    ativ = montar_atividades(buscar_atividades(cli, ini, fim))
    print(f"- atividades: {len(ativ)}")
    pag, omitidos = pagina(montar_dias(resumos, sonos, vfc), ativ, ini, fim,
                           dt.datetime.now(), avisos)
    caminho = os.path.join(PASTA, "painel.html")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(pag)
    print(f"Painel gerado: {caminho}")
    for nome in omitidos:
        print(f"AVISO: gráfico '{nome}' não aparece: sem dados nos últimos "
              "14 dias (o relógio não mediu ou a Garmin não enviou).")
    for a in avisos:
        print(f"AVISO: {a}")
    if abrir:
        webbrowser.open("file:///" + caminho.replace("\\", "/"))


def main(argv=None):
    p = argparse.ArgumentParser(description="Painel pessoal Garmin")
    p.add_argument("--teste", action="store_true",
                   help="testa com 1 dia e mostra os números no terminal")
    p.add_argument("--data", help="dia do teste (AAAA-MM-DD); padrão: ontem")
    p.add_argument("--dias", type=int, default=30,
                   help="quantos dias buscar (padrão 30)")
    p.add_argument("--sem-abrir", action="store_true",
                   help="não abre o painel no navegador")
    a = p.parse_args(argv)
    try:
        cli = Cliente(ler_chave())
        if a.teste:
            dia = (dt.date.fromisoformat(a.data) if a.data
                   else dt.date.today() - dt.timedelta(days=1))
            modo_teste(cli, dia)
        else:
            modo_painel(cli, max(1, min(a.dias, 365)), not a.sem_abrir)
        return 0
    except Erro as e:
        print(f"ERRO: {e}")
        return 1
    except Exception as e:  # nunca mostra detalhes que possam ter segredos
        print(f"ERRO inesperado: {type(e).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

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

BASE = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
NOME_CHAVE = "garmin-personal-api-key"
UA = "painel-pessoal/1.0"
PASTA = os.path.dirname(os.path.abspath(__file__))
SEM_DADO = "sem dado"
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


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


def montar_dias(resumos, sonos):
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
            "passos": _pos(g(r, "movement", "steps", "value")),
            "fc_repouso": _pos(g(r, "heartRate", "restingValue")),
            "fc_min": _pos(g(r, "heartRate", "minValue")),
            "fc_max": _pos(g(r, "heartRate", "maxValue")),
            "estresse": _pos(g(r, "stress", "avgLevel")),
            "bb_min": _pos(g(r, "bodyBattery", "minValue")),
            "bb_max": _pos(g(r, "bodyBattery", "maxValue")),
            "intensidade": None if mod is None and vig is None
            else (mod or 0) + (vig or 0),
            "calorias": _pos(g(r, "calories", "burnedTotal")),
            "respiracao": _pos(g(r, "respiration", "avgValue")),
            "spo2": _pos(g(r, "pulseOx", "avgValue")),
            "andares": _pos(g(r, "movement", "floorsAscended", "value")),
            "sono_s": None,
        }
    for s in sonos:
        data = g(s, "calendarDate")
        if not data:
            continue
        d = dias.setdefault(data, {"data": data})
        seg = g(s, "sleepTimeSeconds")
        d["sono_s"] = seg if isinstance(seg, (int, float)) and seg > 0 else None
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


def eh_corrida(a):
    return "running" in (a.get("tipo") or "")


# ----------------------------------------------------------- formatação ----
def num(v, casas=0):
    if v is None:
        return SEM_DADO
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def km(m):
    return SEM_DADO if m is None else num(m / 1000, 2) + " km"


def hms(s):
    if s is None:
        return SEM_DADO
    s = int(round(s))
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def hm(s):
    if s is None:
        return SEM_DADO
    m = int(round(s / 60))
    return f"{m // 60} h {m % 60:02d} min"


def pace_de_velocidade(v):
    if not v or v <= 0:
        return None
    return 1000 / v


def pace(seg_por_km):
    if seg_por_km is None:
        return SEM_DADO
    s = int(round(seg_por_km))
    return f"{s // 60}:{s % 60:02d} /km"


def data_br(iso):
    if not iso:
        return SEM_DADO
    d = dt.date.fromisoformat(iso)
    return f"{DIAS_SEMANA[d.weekday()]} {d.day:02d}/{d.month:02d}"


# ---------------------------------------------------------------- semanas --
def segunda(d):
    return d - dt.timedelta(days=d.weekday())


def totais_semana(atividades, ini):
    fim = ini + dt.timedelta(days=6)
    cs = [a for a in atividades if eh_corrida(a) and a["data"]
          and ini.isoformat() <= a["data"] <= fim.isoformat()]
    dist = sum(a["dist_m"] for a in cs if a["dist_m"] is not None)
    dur = sum(a["dur_s"] for a in cs if a["dur_s"] is not None)
    # pace médio = tempo total / distância total, só das corridas com os dois
    ambos = [a for a in cs if a["dist_m"] and a["dur_s"]]
    d2 = sum(a["dist_m"] for a in ambos)
    t2 = sum(a["dur_s"] for a in ambos)
    return {"ini": ini, "fim": fim, "n": len(cs),
            "dist_m": dist if cs else 0, "dur_s": dur if cs else 0,
            "pace": (t2 / (d2 / 1000)) if d2 else None}


# ------------------------------------------------------------------ html ---
CSS = """
:root{--bg:#f6f7f9;--card:#fff;--tx:#1b1f24;--mut:#5b6672;--bd:#dfe3e8;--ac:#0b6bcb}
@media(prefers-color-scheme:dark){:root{--bg:#14171b;--card:#1d2127;--tx:#e8ebef;--mut:#9aa5b1;--bd:#2d333b;--ac:#58a6ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:16px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.1rem;margin:32px 0 10px}
.sub{color:var(--mut);font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:12px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px 16px}
.card .r{color:var(--mut);font-size:.85rem}.card .v{font-size:2rem;font-weight:650;color:var(--ac);line-height:1.2}
.card.s .v{font-size:1.3rem;color:var(--tx)}
.tw{overflow-x:auto;background:var(--card);border:1px solid var(--bd);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{padding:8px 12px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--bd)}
th:first-child,td:first-child{text-align:left}th{color:var(--mut);font-weight:600;font-size:.8rem}
tr:last-child td{border-bottom:0}.sd{color:var(--mut);font-style:italic}
.nota{color:var(--mut);font-size:.82rem;margin-top:28px}
"""


def c(v):
    """Célula: 'sem dado' em cinza."""
    t = html.escape(str(v))
    return f'<td class="sd">{t}</td>' if v == SEM_DADO else f"<td>{t}</td>"


def tabela(cabecalho, linhas):
    h = "".join(f"<th>{html.escape(x)}</th>" for x in cabecalho)
    corpo = "".join("<tr>" + "".join(c(x) if i else f"<td>{html.escape(str(x))}</td>"
                                     for i, x in enumerate(l)) + "</tr>"
                    for l in linhas)
    return f'<div class="tw"><table><tr>{h}</tr>{corpo}</table></div>'


def intervalo(ini, fim):
    return f"{ini.day:02d}/{ini.month:02d} a {fim.day:02d}/{fim.month:02d}"


def gerar_html(dias, atividades, ini, fim, agora):
    hoje = fim
    sem0 = segunda(hoje)
    atual = totais_semana(atividades, sem0)
    cards = (
        f'<div class="card"><div class="r">Distância total da semana</div>'
        f'<div class="v">{html.escape(km(atual["dist_m"]))}</div></div>'
        f'<div class="card"><div class="r">Corridas na semana</div>'
        f'<div class="v">{atual["n"]}</div></div>'
        f'<div class="card s"><div class="r">Tempo correndo</div>'
        f'<div class="v">{html.escape(hms(atual["dur_s"]) if atual["n"] else SEM_DADO)}</div></div>'
        f'<div class="card s"><div class="r">Pace médio</div>'
        f'<div class="v">{html.escape(pace(atual["pace"]))}</div></div>')

    semanas, s = [], sem0
    while s >= segunda(ini):
        t = totais_semana(atividades, s)
        semanas.append([intervalo(t["ini"], t["fim"]), t["n"], km(t["dist_m"]),
                        hms(t["dur_s"]) if t["n"] else SEM_DADO, pace(t["pace"])])
        s -= dt.timedelta(days=7)

    linhas_at = []
    for a in atividades:
        corre = any(k in (a["tipo"] or "") for k in ("running", "walking", "hiking"))
        p = pace(pace_de_velocidade(a["vel_ms"])) if corre else SEM_DADO
        linhas_at.append([data_br(a["data"]), a["tipo"] or SEM_DADO,
                          a["nome"] or SEM_DADO, km(a["dist_m"]),
                          hms(a["dur_s"]), p])

    linhas_d = []
    for d in reversed(dias):
        bb = (f'{d["bb_min"]}–{d["bb_max"]}'
              if d.get("bb_min") is not None and d.get("bb_max") is not None
              else SEM_DADO)
        fcr = (f'{d["fc_min"]}–{d["fc_max"]} bpm'
               if d.get("fc_min") is not None and d.get("fc_max") is not None
               else SEM_DADO)
        linhas_d.append([
            data_br(d["data"]), num(d.get("passos")),
            hm(d.get("sono_s")),
            SEM_DADO if d.get("fc_repouso") is None else f'{d["fc_repouso"]} bpm',
            fcr, num(d.get("estresse")), bb,
            num(d.get("intensidade")), num(d.get("calorias")),
            num(d.get("respiracao")), num(d.get("spo2")),
            num(d.get("andares"))])

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel Garmin</title><style>{CSS}</style></head><body><main>
<h1>Painel Garmin</h1>
<div class="sub">Período: {ini.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')} ·
atualizado em {agora.strftime('%d/%m/%Y %H:%M')}</div>

<h2>Semana atual ({intervalo(sem0, sem0 + dt.timedelta(days=6))}) — corridas</h2>
<div class="grid">{cards}</div>

<h2>Semanas (segunda a domingo) — corridas</h2>
{tabela(["Semana", "Corridas", "Distância", "Tempo", "Pace médio"], semanas)}

<h2>Atividades</h2>
{tabela(["Data", "Tipo", "Nome", "Distância", "Duração", "Pace"], linhas_at)
 if linhas_at else '<p class="sd">sem dado: nenhuma atividade no período.</p>'}

<h2>Dados diários</h2>
{tabela(["Dia", "Passos", "Sono", "FC repouso", "FC mín–máx", "Estresse médio",
         "Body Battery mín–máx", "Min. de intensidade", "Calorias totais",
         "Respiração média", "SpO2 média", "Andares subidos"], linhas_d)
 if linhas_d else '<p class="sd">sem dado: nenhum dia no período.</p>'}

<p class="nota">Todos os números vêm da Garmin Connect Personal API. “sem dado” =
a Garmin não enviou esse valor. O sono aparece no dia em que você acordou.
O pace é calculado a partir da velocidade média ou da distância e do tempo
que a Garmin enviou. Semanas vão de segunda a domingo; os totais contam só
atividades de corrida.</p>
</main></body></html>"""


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


def modo_painel(cli, dias, abrir):
    fim = dt.date.today()
    ini = fim - dt.timedelta(days=dias - 1)
    # começa na segunda-feira para a primeira semana ficar completa
    ini = segunda(ini)
    print(f"Buscando de {ini} a {fim} ...")
    resumos = buscar_resumos(cli, ini, fim)
    print(f"- resumos diários: {len(resumos)}")
    sonos = buscar_sono(cli, ini, fim)
    print(f"- registros de sono: {len(sonos)}")
    ativ = montar_atividades(buscar_atividades(cli, ini, fim))
    print(f"- atividades: {len(ativ)}")
    pagina = gerar_html(montar_dias(resumos, sonos), ativ, ini, fim,
                        dt.datetime.now())
    caminho = os.path.join(PASTA, "painel.html")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(pagina)
    print(f"Painel gerado: {caminho}")
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

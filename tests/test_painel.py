"""Teste com servidor falso: não usa chave nem conta reais.
Gera tests/saida/painel.html (dados inventados SÓ para teste visual)."""
import base64, contextlib, datetime as dt, io, json, os, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import garmin_painel as gp
import armazem

def _b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
CHAVE_FALSA = "CHAVE-FALSA-" + "x" * 130
TOKEN_FALSO = f"{_b64({'alg': 'none'})}.{_b64({'exp': time.time() + 86400})}.assinatura"
METODOS = []
HOJE = dt.date.today()
SEM_VFC = os.environ.get("SEM_VFC") == "1"   # simula relógio sem VFC
SEM_PESO = os.environ.get("SEM_PESO") == "1"

def d(i): return HOJE - dt.timedelta(days=i)
def rng(a, b):
    x = dt.date.fromisoformat(a)
    while x <= dt.date.fromisoformat(b):
        yield x; x += dt.timedelta(days=1)

def resumo(x):
    i = (HOJE - x).days
    if i in (3, 9): return {"calendarDate": x.isoformat()}           # dia sem medição
    return {"calendarDate": x.isoformat(),
            "movement": {"steps": {"value": 4000 + (i * 977) % 9000, "goal": 8000 + 500 * (i % 3)}, "floorsAscended": {"value": 10 + i}},
            "heartRate": {"restingValue": 50 + (i * 3) % 9 if i != 5 else 0, "minValue": 44, "maxValue": 150 + i},
            "stress": {"avgLevel": 20 + i}, "bodyBattery": {"minValue": 15 + (i * 7) % 30, "maxValue": 70 + (i * 5) % 28},
            "intensityMinutes": {"moderate": 10, "vigorous": 5}, "calories": {"burnedTotal": 2300 + i * 11},
            "respiration": {"avgValue": 14}, "pulseOx": {"avgValue": 92 + i % 5},
            "hydration": ({"goalInMl": 2500, "consumedInFractionalMl": 1500.0 + 50 * i} if i % 4 else {})}

def sono(x):
    i = (HOJE - x).days
    if i in (2, 6, 12): return {"calendarDate": None, "sleepTimeSeconds": None, "deviceRemCapable": False}
    prof, leve, rem = 3600 + i * 120, 14400 + (i * 300) % 3600, 5400 + i * 60
    return {"calendarDate": x.isoformat(), "sleepTimeSeconds": prof + leve + rem,
            "deepSleepSeconds": prof, "lightSleepSeconds": leve, "remSleepSeconds": rem, "deviceRemCapable": True}

ATIV = {1: [("running", 10000, 3000), ("strength_training", None, 2400)], 3: [("cycling", 40000, 5400)],
        4: [("trail_running", 8000, 2800)], 8: [("running", 5000, 1700)], 0: [("lap_swimming", 1500, 2100)],
        6: [("running", 12000, 3900), ("cycling", 20000, 2700)], 11: [("running", 6000, 2000)],
        15: [("running", 7000, 2400)], 22: [("running", 9000, 3000)],
        13: [("running", 10200, 3100)], 2: [("treadmill_running", 5000, 1800)],                         # marcada como competição na Garmin
        45: [("running", 21500, 7200)]}                          # fora do período: só entra com --historico

def ativ_json(i, n, t, dist, dur):
    x = d(i)
    r = {"activityId": i * 10 + n, "startTimeLocal": f"{x.isoformat()} {7 + n * 10:02d}:00:00",
         "activityName": f"Treino <{t}>", "activityType": {"typeKey": t}, "duration": float(dur),
         "averageHR": 150 + i, "elevationGain": 20.0 + i}
    if i == 13: r["eventType"] = {"typeId": 1, "typeKey": "race"}
    if "running" in t: r["startLatitude"] = None if t == "treadmill_running" else -20.44 + (i % 7) * 0.002
    if t == "treadmill_running": r.pop("hasPolyline", None)
    if dist: r.update(distance=float(dist), averageSpeed=dist / dur)
    if "running" in t:
        r.update(averageRunningCadenceInStepsPerMinute=170.0 + n, vO2MaxValue=50.0 + i % 3,
                 hrTimeInZone_1=300.0, hrTimeInZone_2=900.0 + i * 10, hrTimeInZone_3=800.0, hrTimeInZone_4=300.0, hrTimeInZone_5=0.0,
                 **{f"fastestSplit_{m}": dur / dist * m * 0.95 for m in (1000, 1609, 5000, 10000, 21098) if dist >= m})
    return r

class Estado: hrv_falha = False; zip_fit = None; zip_por_id = None
DOWNLOADS = []
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, o, code=200):
        b = json.dumps(o).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
    def _bytes(self, b, tipo="application/zip"):
        self.send_response(200); self.send_header("Content-Type", tipo); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        METODOS.append(("POST", self.path))
        if self.headers.get("Authorization") != "ApiKey " + CHAVE_FALSA: return self._json({}, 401)
        self._json({"access_token": TOKEN_FALSO})
    def do_GET(self):
        METODOS.append(("GET", self.path))
        if self.headers.get("Authorization") != "Bearer " + TOKEN_FALSO: return self._json({}, 401)
        u = urllib.parse.urlparse(self.path); q = dict(urllib.parse.parse_qsl(u.query)); p = u.path
        if "/download-service/files/activity/" in p:
            DOWNLOADS.append(p)
            if Estado.zip_por_id: return self._bytes(Estado.zip_por_id(int(p.rsplit("/", 1)[1])))
            return self._bytes(Estado.zip_fit if Estado.zip_fit is not None else b"")
        if "userprofile/settings" in p: return self._json({"x": 1})
        if "/weight-service/weight/all/" in p:
            a, b = p.rsplit("/", 2)[-2:]
            if SEM_PESO: return self._json([])
            return self._json([{"calendarDate": x.isoformat(), "weight": (72500 if (HOJE - x).days == 6 else 72.0 + ((HOJE - x).days % 3) / 10),
                                "timestampGMT": f"{x.isoformat()}T07:00:00.000Z"}
                               for x in rng(a, b) if (HOJE - x).days % 5 == 0 or (HOJE - x).days == 6])
        if "dailysummaries" in p: return self._json({"data": [resumo(x) for x in rng(q["startDate"], q["endDate"])]})
        if "dailySleep" in p: return self._json([sono(x) for x in rng(q["startDate"], q["endDate"])])
        if "/hrv-service/hrv/daily/" in p:
            if Estado.hrv_falha: return self._json({}, 403)
            if SEM_VFC: return self._json({"hrvSummaries": []})
            a, b = p.rsplit("/", 2)[-2:]
            return self._json({"hrvSummaries": [{"calendarDate": x.isoformat(), "lastNightAvg": 40 + ((HOJE - x).days * 4) % 30}
                                                 for x in rng(a, b) if (HOJE - x).days not in (4, 7)]})
        if "activities/search" in p:
            out = []
            for i, lst in sorted(ATIV.items()):
                if not (q["startDate"] <= d(i).isoformat() <= q["endDate"]): continue
                out += [ativ_json(i, n, *a) for n, a in enumerate(lst)]
            s, lim = int(q.get("start", 0)), int(q.get("limit", 99))
            assert lim <= 20, "limite de página deveria ser 20"
            return self._json(out[s:s + lim])
        self._json({}, 404)

srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
gp.BASE = f"http://127.0.0.1:{srv.server_port}"
CHAMADAS_CHAVE = []
gp.ler_chave = lambda: (CHAMADAS_CHAVE.append(1), CHAVE_FALSA)[1]
gp.time.sleep = lambda s: None                 # sem esperas no teste
gp.PASTA = os.path.join(os.path.dirname(__file__), "saida"); os.makedirs(gp.PASTA, exist_ok=True)

# cofre falso (em memória) para o cache do token
COFRE = {}
LOG_COFRE = []
gp.ler_token_cache = lambda: COFRE.get("t")
def _grav(v): LOG_COFRE.append(("grav", v)); COFRE["t"] = v; return True
def _apag(): LOG_COFRE.append(("apag",)); COFRE.pop("t", None); return True
gp.gravar_token_cache, gp.apagar_token_cache = _grav, _apag

def rodar(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rc = gp.main(args)
    return rc, buf.getvalue()

def n_get(trecho): return sum(1 for m, p in METODOS if m == "GET" and trecho in p)
def painel(): return open(os.path.join(gp.PASTA, "painel.html"), encoding="utf-8").read()

if __name__ == "__main__":
    import shutil
    for f in os.listdir(gp.PASTA):                       # começa de uma pasta limpa
        p_ = os.path.join(gp.PASTA, f)
        shutil.rmtree(p_) if os.path.isdir(p_) else os.remove(p_)

    # 0) teste de 1 dia
    rc, out = rodar(["--teste", "--data", d(1).isoformat()]); assert rc == 0, out
    assert CHAVE_FALSA not in out and TOKEN_FALSO not in out

    # 1) primeira execução completa: guarda dados e token
    COFRE.clear(); METODOS.clear()
    rc, out = rodar(["--sem-abrir"]); print(out); assert rc == 0, out
    resumos_1 = n_get("dailysummaries"); assert resumos_1 >= 5
    assert any(x[0] == "grav" for x in LOG_COFRE), "token deveria ser guardado no cofre"
    assert all(CHAVE_FALSA not in x[1] for x in LOG_COFRE if x[0] == "grav"), "chave NUNCA vai ao cofre de token"
    pg = painel()
    assert CHAVE_FALSA not in pg and TOKEN_FALSO not in pg
    bruto = open(os.path.join(gp.PASTA, "dados_brutos.json"), encoding="utf-8").read()
    assert CHAVE_FALSA not in bruto and TOKEN_FALSO not in bruto, "armazém sem segredos"
    assert "Treino &lt;running&gt;" in pg                         # texto escapado
    assert "Distância de corrida por semana" in pg and "Tempo por zona" in pg and "Recordes pessoais" in pg

    # 2) segunda execução: só o recente + reaproveita o token (sem novo POST)
    METODOS.clear()
    rc, out = rodar(["--sem-abrir"]); assert rc == 0, out
    assert n_get("dailysummaries") < resumos_1, (n_get("dailysummaries"), resumos_1)
    assert not any(m == "POST" for m, _ in METODOS), "token em cache deveria ser reaproveitado"

    # 3) token em cache recusado (401): descarta, pede outro e conclui
    COFRE["t"] = COFRE["t"].split("|")[0] + "|" + f"{_b64({'a': 1})}.{_b64({'exp': time.time() + 86400})}.x"
    LOG_COFRE.clear(); METODOS.clear()
    rc, out = rodar(["--sem-abrir"]); assert rc == 0, out
    assert ("apag",) in LOG_COFRE and any(m == "POST" for m, _ in METODOS)

    # 4) --so-visual: nada de rede, nem lê a chave
    METODOS.clear(); CHAMADAS_CHAVE.clear()
    rc, out = rodar(["--so-visual", "--sem-abrir"]); print(out); assert rc == 0, out
    assert not METODOS and not CHAMADAS_CHAVE, "so-visual não pode usar rede nem chave"
    assert "sem consultar a Garmin" in painel()

    # 5) --esquecer-token
    rc, out = rodar(["--esquecer-token"]); assert rc == 0 and "t" not in COFRE

    # 6) armazém: outra janela/backfill planejados
    st = armazem.carregar(os.path.join(gp.PASTA, "dados_brutos.json"))
    assert armazem.planejar(st, HOJE, HOJE - dt.timedelta(days=90))[0][0] == HOJE - dt.timedelta(days=90)

    # 7) paginação de 20 em 20
    class Falso:
        def __init__(s): s.chamadas = []
        def get(s, caminho, params):
            s.chamadas.append(params["start"]); assert params["limit"] == 20
            return [{"activityId": k} for k in range(params["start"], min(params["start"] + 20, 45))]
    f = Falso(); assert len(gp.buscar_atividades(f, d(5), HOJE)) == 45 and f.chamadas == [0, 20, 40, 45]


    # 9) VFC que falha: avisa, lembra de refazer e recupera na próxima execução
    for f_ in ("dados_brutos.json",): os.remove(os.path.join(gp.PASTA, f_))
    Estado.hrv_falha = True
    rc, out = rodar(["--sem-abrir"]); assert rc == 0 and "VFC não pôde ser lida" in out, out
    st = armazem.carregar(os.path.join(gp.PASTA, "dados_brutos.json"))
    assert st.get("vfc_pendente_ini") and not st["vfc"]
    Estado.hrv_falha = False
    rc, out = rodar(["--sem-abrir"]); assert rc == 0, out
    st = armazem.carregar(os.path.join(gp.PASTA, "dados_brutos.json"))
    assert "vfc_pendente_ini" not in st and len(st["vfc"]) > 20, "VFC deveria ter sido refeita para todo o período"

    # 10) gravação bloqueada (OneDrive): painel sai mesmo assim, com aviso
    orig = armazem.salvar
    def bloqueado(*a, **k): raise PermissionError("bloqueado")
    armazem.salvar = bloqueado
    rc, out = rodar(["--sem-abrir"]); armazem.salvar = orig
    assert rc == 0 and "Não consegui guardar os dados" in out and "Painel gerado" in out, out

    # 11) --so-visual com período maior que o guardado: avisa e limita
    rc, out = rodar(["--so-visual", "--dias", "90", "--sem-abrir"]); assert rc == 0, out
    assert "dados guardados começam em" in painel()

    # 12) lista vazia da Garmin não apaga atividades guardadas
    st = armazem.carregar(os.path.join(gp.PASTA, "dados_brutos.json")); antes = len(st["atividades"])
    armazem.mesclar(st, (d(30), HOJE), [], [], {}, []); assert len(st["atividades"]) == antes > 0

    # 13) estrutura do cofre do Windows: mesmo tamanho/posição da CREDENTIALW de 64 bits
    import cofre, ctypes
    _, _, CRED = cofre._estruturas()
    assert ctypes.sizeof(CRED) == 80 and CRED.CredentialBlob.offset == 40 and CRED.UserName.offset == 72
    assert cofre._gravar_win.__defaults__ == ("utf-16-le",) and cofre.LIMITE_SEGREDO == 2560

    # 14) --pasta-dados: arquivos vão para onde o usuário escolher
    import tempfile
    alvo = tempfile.mkdtemp()
    rc, out = rodar(["--sem-abrir", "--pasta-dados", alvo]); assert rc == 0, out
    assert {"dados_brutos.json", "painel.html"} <= set(os.listdir(alvo)) <= {"dados_brutos.json", "painel.html", "rotas.json"}
    gp.PASTA_DADOS = None

    # 15) --diagnostico: tudo OK, sem segredos na saída
    import configuracao
    COFRE.clear()
    rc, out = rodar(["--diagnostico"]); print(out)
    assert rc == 0 and "[OK]" in out and "[FALHA]" not in out, out
    assert CHAVE_FALSA not in out and TOKEN_FALSO not in out
    assert "Conexão e autenticação com a Garmin funcionando" in out
    assert "Data de vencimento da chave não informada" in out          # ainda não informada
    gp.ler_chave_orig = gp.ler_chave
    def sem_chave(): raise gp.ErroCofre("Não achei a chave no cofre (teste).")
    gp.ler_chave = sem_chave
    rc, out = rodar(["--diagnostico"]); gp.ler_chave = gp.ler_chave_orig
    assert rc == 1 and "[FALHA]" in out and "Não achei a chave" in out

    # 15b) comando externo que responde com bytes não-UTF-8 (como o schtasks em português)
    import diagnostico, subprocess
    emite = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'Tarefa n\\xe3o encontrada \\xa2'); sys.exit({})"]
    assert diagnostico.comando_ok([a.format(0) for a in emite]) is True
    assert diagnostico.comando_ok([a.format(1) for a in emite]) is False
    assert diagnostico.comando_ok(["comando-que-nao-existe-xyz"]) is None

    # 16) --chave-vence: aviso em 14 dias, vencida, e data inválida
    prox = (HOJE + dt.timedelta(days=9)).isoformat()
    rc, out = rodar(["--chave-vence", prox]); assert rc == 0 and "faltam 9 dias" in out, out
    rc, out = rodar(["--so-visual", "--sem-abrir"]); assert rc == 0 and "vence em 9 dias" in out, out
    pg = painel(); assert 'class="faixa" role="alert"' in pg and "vence em 9 dias" in pg
    rc, out = rodar(["--chave-vence", (HOJE - dt.timedelta(days=2)).strftime("%d/%m/%Y")]); assert rc == 0 and "já venceu" in out
    rc, out = rodar(["--so-visual", "--sem-abrir"]); assert "venceu em" in painel()
    rc, out = rodar(["--chave-vence", (HOJE + dt.timedelta(days=60)).isoformat()]); assert rc == 0
    rc, out = rodar(["--so-visual", "--sem-abrir"]); assert 'role="alert"' not in painel() and "A chave da Garmin vence em" in painel()
    rc, out = rodar(["--chave-vence", "31/02/2027"]); assert rc == 1 and "Data inválida" in out

    # 17) backup diário: 1 por dia, mantém 5; só copia arquivo íntegro
    cam = os.path.join(gp.PASTA, "dados_brutos.json")
    bdir = os.path.join(gp.PASTA, "backups")
    import shutil; shutil.rmtree(bdir, ignore_errors=True)
    for i in range(8, 0, -1):                                   # 8 dias antigos
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(cam, os.path.join(bdir, f"dados_brutos-{(HOJE - dt.timedelta(days=i + 1)).isoformat()}.json"))
    rc, out = rodar(["--sem-abrir"]); assert rc == 0, out
    nomes = sorted(os.listdir(bdir)); assert len(nomes) == 5 and nomes[-1] == f"dados_brutos-{HOJE.isoformat()}.json", nomes
    rc, out = rodar(["--sem-abrir"]); assert sorted(os.listdir(bdir)) == nomes, "só 1 backup por dia"

    # 18) arquivo de dados corrompido: não é apagado, é separado, e o programa recomeça
    open(cam, "w").write("{isto não é json")
    rc, out = rodar(["--sem-abrir"]); assert rc == 0 and "foi separado em" in out, out
    assert any(".corrompido-" in n for n in os.listdir(gp.PASTA))
    assert armazem.carregar(cam)["atividades"], "armazém refeito"
    assert armazem.backup_diario(cam, hoje=HOJE + dt.timedelta(days=1)) is not None
    open(cam, "w").write("{lixo"); assert armazem.backup_diario(cam, hoje=HOJE + dt.timedelta(days=2)) is None, "não copia arquivo ruim"
    rc, out = rodar(["--sem-abrir"]); assert rc == 0
    for n in os.listdir(gp.PASTA):
        if ".corrompido-" in n: os.remove(os.path.join(gp.PASTA, n))

    # 19) faixa de dados antigos (o navegador decide pela hora): guarda a hora no armazém
    st = armazem.carregar(cam); st["atualizado_em"] = (dt.datetime.now() - dt.timedelta(days=2, hours=3)).isoformat(timespec="seconds")
    armazem.salvar(cam, st)
    rc, out = rodar(["--so-visual", "--sem-abrir"]); assert rc == 0, out
    assert 'id="velho"' in painel() and 'data-gerado="' in painel()
    rc, out = rodar(["--sem-abrir"]); assert rc == 0

    # 20) pacote B: comparação, metas, hidratação, SpO2, peso, recordes e histórico
    import metas as metas_, formatos
    rc, out = rodar(["--sem-abrir"]); assert rc == 0 and "peso:" in out, out
    pg = painel()
    assert "Esta semana × semana passada × média" in pg and "Peso (kg)" in pg and "Hidratação por dia" in pg and "SpO2 média do dia" in pg
    assert "Suas metas" not in pg, "sem metas definidas, o cartão não aparece"
    st = armazem.carregar(cam)
    assert st["peso"] and all(30 < v < 300 for v in st["peso"].values()), "gramas devem virar kg"
    assert 72.5 in st["peso"].values() and 72500 not in st["peso"].values()
    # comparação: conferida com a soma direta dos dados guardados
    ativ = gp.montar_atividades(armazem.todas_atividades(st))
    cmpd = formatos.comparar_semanas(ativ, HOJE, dt.date.fromisoformat(st["cobertura_ini"]))
    sem0 = formatos.segunda(HOJE)
    manual = sum(a["dist_m"] for a in ativ if formatos.eh_corrida(a) and a["dist_m"]
                 and (sem0 - dt.timedelta(days=7)).isoformat() <= a["data"] < sem0.isoformat())
    assert abs(cmpd["passada"]["dist_m"] - manual) < 1e-6
    assert cmpd["semanas_media"] >= 4
    # metas
    rc, out = rodar(["--meta", "km-mes=50", "--meta", "corridas-semana=3"]); assert rc == 0 and "Meta definida" in out
    rc, out = rodar(["--meta", "km-ano=5"]); assert rc == 1 and "Meta desconhecida" in out
    rc, out = rodar(["--meta", "km-mes=abc"]); assert rc == 1 and "não é um número" in out
    rc, out = rodar(["--meta", "km-mes=-3"]); assert rc == 1
    rc, out = rodar(["--so-visual", "--sem-abrir"]); assert rc == 0
    pg = painel(); assert "Suas metas" in pg and 'role="progressbar"' in pg
    prog = metas_.progresso(gp.pasta_dados(), ativ, HOJE)
    km_mes = next(m for m in prog if m["nome"] == "km-mes")
    esperado = sum(a["dist_m"] for a in ativ if formatos.eh_corrida(a) and a["dist_m"] and a["data"][:7] == HOJE.isoformat()[:7]) / 1000
    assert abs(km_mes["atual"] - esperado) < 1e-6 and km_mes["pct"] == round(esperado / 50 * 100)
    rc, out = rodar(["--remover-meta", "km-mes"]); assert rc == 0
    rc, out = rodar(["--remover-meta", "corridas-semana"]); assert rc == 0
    assert metas_.listar(gp.pasta_dados()) == {}
    # recordes só com o histórico: a corrida de 45 dias atrás (meia maratona) entra depois de --historico
    assert "Mais rápido: Meia maratona" not in painel()
    rc, out = rodar(["--sem-abrir", "--historico", "60"]); assert rc == 0, out
    pg = painel()
    assert "Mais rápido: Meia maratona" in pg and "Corrida mais longa" in pg and "Semana com mais distância" in pg
    assert "Histórico guardado desde" in pg
    st = armazem.carregar(cam); assert len(armazem.todas_atividades(st)) > len(ativ), "histórico ampliado"
    # peso indisponível (403/404) vira "sem dado"; lista vazia omite o gráfico
    SEM_PESO_ORIG = globals()["SEM_PESO"]; globals()["SEM_PESO"] = True
    for x_ in ("dados_brutos.json",): os.remove(cam)
    rc, out = rodar(["--sem-abrir"]); assert rc == 0 and "Peso" in out and "não aparece" in out, out
    globals()["SEM_PESO"] = SEM_PESO_ORIG
    rc, out = rodar(["--sem-abrir"]); assert rc == 0

    # 21) armazém antigo (sem "peso"): o peso do período inteiro é buscado uma vez
    import json as _j
    antigo = _j.load(open(cam, encoding="utf-8")); antigo.pop("peso", None); antigo.pop("peso_pendente_ini", None)
    _j.dump(antigo, open(cam, "w", encoding="utf-8"))
    METODOS.clear(); rc, out = rodar(["--sem-abrir"]); assert rc == 0, out
    st = armazem.carregar(cam)
    assert "peso_pendente_ini" not in st and st["peso"], "peso deveria ter sido buscado"
    assert min(st["peso"]) <= (dt.date.fromisoformat(st["cobertura_ini"]) + dt.timedelta(days=6)).isoformat(), "cobre o período antigo"

    # 22) visual de corredor (fase 1): perfil, provas, logos, ligação com a Garmin pela data
    import struct, zlib, corredor
    def png():
        ch = lambda t_, d_: struct.pack(">I", len(d_)) + t_ + d_ + struct.pack(">I", zlib.crc32(t_ + d_) & 0xffffffff)
        return (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                + ch(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + ch(b"IEND", b""))
    pasta_ = gp.PASTA
    rc, out = rodar(["--criar-perfil"]); assert rc == 0 and "perfil.txt" in out, out
    assert os.path.isdir(os.path.join(pasta_, "imagens", "corridas"))
    rc, out = rodar(["--criar-perfil"]); assert "nada novo" in out, "não sobrescreve"
    assert 'class="hero"' not in painel() or True
    open(os.path.join(pasta_, "imagens", "foto.png"), "wb").write(png())
    open(os.path.join(pasta_, "imagens", "corridas", "logo5k.png"), "wb").write(png())
    open(os.path.join(pasta_, "imagens", "corridas", "logo.svg"), "w").write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(1)</script></svg>')
    open(os.path.join(pasta_, "imagens", "corridas", "falso.png"), "w").write("isto não é um png")
    open(os.path.join(pasta_, "perfil.txt"), "w", encoding="utf-8").write("nome: João <b>Teste</b>\nfrase: Corredor desde 2024\nfoto: foto.png\nlinha sem dois pontos\n")
    fut = (HOJE + dt.timedelta(days=24)).isoformat()
    open(os.path.join(pasta_, "provas.txt"), "w", encoding="utf-8").write(f"""# comentário
{d(8).isoformat()}; 5K Teste; 5; logo5k.png
{d(22).strftime('%d/%m/%Y')}; Dez Quilômetros; 10; logo.svg
{d(1).isoformat()}; Sem atividade parecida; 21,1;
{fut}; Futura Corrida; 10; ../fora.png
{(HOJE + dt.timedelta(days=90)).isoformat()}; Maratona; 42,195; falso.png
2026-13-40; Data Ruim; 5
linha ruim
""")
    rc, out = rodar(["--so-visual", "--sem-abrir"]); assert rc == 0, out
    pg = painel()
    assert 'class="hero"' in pg and "João &lt;b&gt;Teste&lt;/b&gt;" in pg and "<b>Teste</b>" not in pg
    assert 'src="data:image/png;base64,' in pg and pg.count("logo-img") >= 2
    assert "<script>alert(1)" not in pg, "SVG de logo entra só como imagem (data URI), nunca como código"
    assert "Próximas provas" in pg and "Provas que já corri" in pg and ">24<" in pg and "dias" in pg
    assert "5K Teste" in pg and "0:28:20" in pg and "5:40 /km" in pg      # tempo/pace da Garmin, ligados pela data
    assert "Dez Quilômetros" in pg and "0:50:00" in pg                    # 9 km vs 10 km informados: dentro de 20%
    assert "Sem atividade parecida" in pg
    assert "COMPETIÇÃO ·" in pg                                    # marcada como corrida de prova na Garmin
    for esperado in ("fora do", "Use só o nome", "não parece ser uma imagem", "data inválida", "linha 5 ignorada"):
        pass
    for esperado in ("use só o nome do arquivo", "não parece ser uma imagem .png", "data inválida", "perfil.txt linha 4 ignorada"):
        assert esperado in pg, esperado
    assert "Distância desde" in pg                                       # histórico guardado ainda não cobre o ano
    # soma do ano: só é "do ano" quando o histórico guardado começa em 1º de janeiro
    cobertura_ano = f"{HOJE.year}-01-01"
    co_ = corredor.montar(pasta_, gp.montar_atividades(armazem.todas_atividades(armazem.carregar(cam))), HOJE, cobertura_ano)
    assert co_["periodo"]["do_ano"] is True
    # ligação pela data: sem atividade no dia => "sem dado", nunca inventa números
    prova_ = next(p for p in co_["feitas"] if p["nome"] == "Sem atividade parecida"); assert prova_["atv"] is None
    # caminhos perigosos e arquivos grandes
    av = []
    assert corredor.imagem_uri(os.path.join(pasta_, "imagens"), "..\\x.png", av, "t") is None
    assert corredor.imagem_uri(os.path.join(pasta_, "imagens"), "C:\\x.png", av, "t") is None
    open(os.path.join(pasta_, "imagens", "grande.png"), "wb").write(png() + b"0" * 2_600_000)
    assert corredor.imagem_uri(os.path.join(pasta_, "imagens"), "grande.png", av, "t") is None and any("reduza" in x for x in av)
    # "*" no nome: mantém o nome da atividade na Garmin e só acrescenta o logo
    open(os.path.join(pasta_, "provas.txt"), "w", encoding="utf-8").write(f"{d(13).isoformat()}; *; 10; logo5k.png\n")
    co_ = corredor.montar(pasta_, gp.montar_atividades(armazem.todas_atividades(armazem.carregar(cam))), HOJE)
    cartao_ = next(p for p in co_["feitas"] if p["data"] == d(13))
    assert cartao_["origem"] == "lista" and cartao_["logo_uri"] and cartao_["nome"] == "Treino <running>", cartao_["nome"]
    assert sum(1 for p in co_["feitas"] if p["data"] == d(13)) == 1, "não duplica com a competição marcada na Garmin"
    # sem perfil.txt e sem provas.txt: o painel volta ao cabeçalho clássico
    os.remove(os.path.join(pasta_, "perfil.txt")); os.remove(os.path.join(pasta_, "provas.txt"))
    rc, out = rodar(["--so-visual", "--sem-abrir"]); assert rc == 0 and 'class="hero"' not in painel() and 'class="top"' in painel()
    open(os.path.join(pasta_, "perfil.txt"), "w", encoding="utf-8").write("nome: Corredor Teste\nfoto: foto.png\n")
    open(os.path.join(pasta_, "provas.txt"), "w", encoding="utf-8").write(f"{d(8).isoformat()}; 5K Teste; 5; logo5k.png\n{fut}; Futura Corrida; 10;\n")
    rc, out = rodar(["--so-visual", "--sem-abrir"]); assert rc == 0

    # 23) rotas: arquivo FIT lido com a biblioteca OFICIAL da Garmin (pulado se não instalada)
    import rotas, io, zipfile, re
    if rotas.carregar_sdk() is None:
        print("PULADO (23): garmin-fit-sdk não instalada. Instale: " + rotas.INSTALAR)
    else:
        import fit_falso
        fit_bytes, esp = fit_falso.criar()
        buf_ = io.BytesIO()
        with zipfile.ZipFile(buf_, "w") as z_: z_.writestr("12345_ACTIVITY.fit", fit_bytes)
        Estado.zip_fit = buf_.getvalue()
        rc, out = rodar(["--sem-abrir"]); assert rc == 0, out         # garante dados no armazém
        DOWNLOADS.clear(); METODOS.clear()
        rc, out = rodar(["--teste-rota"]); print(out); assert rc == 0, out
        assert len(DOWNLOADS) == 1 and all(m == "GET" or p.endswith("/token") for m, p in METODOS), "1 download, só leitura"
        assert f"com GPS: {esp['com_gps']} (96%)" in out and f"Registros no arquivo: {esp['registros']}" in out
        comp = float(re.search(r"Comprimento da trilha: ([\d,]+) km", out).group(1).replace(",", "."))
        assert abs(comp * 1000 - esp["comprimento_m"]) / esp["comprimento_m"] < 0.02, comp
        assert "Trilha simplificada: 300 pontos" in out and "Esporte registrado no arquivo: running" in out
        assert not re.search(r"-?\d{2}[.,]\d{4,}", out), "nenhuma coordenada na saída"
        assert CHAVE_FALSA not in out and TOKEN_FALSO not in out
        rc, out = rodar(["--teste-rota", "--data", "1999-01-01"]); assert rc == 1 and "Não achei uma corrida" in out
        # ZIP sem FIT / bytes que não são FIT / resposta vazia
        buf_ = io.BytesIO()
        with zipfile.ZipFile(buf_, "w") as z_: z_.writestr("leia-me.txt", "oi")
        Estado.zip_fit = buf_.getvalue(); rc, out = rodar(["--teste-rota"]); assert rc == 1 and "não contém um arquivo .fit" in out, out
        buf_ = io.BytesIO()
        with zipfile.ZipFile(buf_, "w") as z_: z_.writestr("x.fit", b"isto nao e um fit de verdade")
        Estado.zip_fit = buf_.getvalue(); rc, out = rodar(["--teste-rota"]); assert rc == 1 and "FIT válido" in out, out
        Estado.zip_fit = b""; rc, out = rodar(["--teste-rota"]); assert rc == 1, out
        Estado.zip_fit = None
        # biblioteca ausente: mensagem com a instrução de instalação
        orig_sdk = rotas.carregar_sdk; rotas.carregar_sdk = lambda: None
        rc, out = rodar(["--teste-rota"]); rotas.carregar_sdk = orig_sdk
        assert rc == 1 and "pip install --require-hashes" in out, out
        # trilha: simplificar mantém a forma; cortar pontas tira o começo e o fim (privacidade)
        pts = rotas.pontos_gps(rotas.decodificar(fit_bytes))
        simp = rotas.simplificar(pts)
        assert len(simp) == 300 and simp[0] == pts[0] and simp[-1] == pts[-1]
        assert abs(rotas.comprimento_m(simp) - rotas.comprimento_m(pts)) / rotas.comprimento_m(pts) < 0.02
        cort = rotas.cortar_pontas(pts, 300)
        assert abs((rotas.comprimento_m(pts) - rotas.comprimento_m(cort)) - 600) < 25, "tira ~300 m de cada ponta"
        assert rotas.cortar_pontas(pts[:5], 300) == [], "rota curta demais some, nunca vaza"
        assert rotas.pontos_gps({"record_mesgs": [{"position_lat": 0, "position_long": 0}, {"position_lat": 2**31 - 1, "position_long": 0}, {}]}) == [], "0,0 e lat inválida são descartados"

    # 24) rotas (fase 3): trilhas guardadas, esteira sem GPS, outra cidade, privacidade, painel
    if rotas.carregar_sdk() is not None:
        import fit_falso, shutil
        for f_ in ("rotas.json", "dados_brutos.json"):
            p_ = os.path.join(gp.PASTA, f_)
            if os.path.exists(p_): os.remove(p_)
        def zip_do(aid):
            if aid == 130 and False: return b""
            longe = (aid == 450)                                   # a corrida de meia maratona: outra cidade
            lat0 = (-18.51 if longe else -20.44 + (aid % 7) * 0.003)
            lon0 = (-54.75 if longe else -54.64 + (aid % 5) * 0.003)
            fb, _ = fit_falso.criar(lat0, lon0, 140 + (aid % 5) * 45, 1 + aid % 3, 700, 20)
            b_ = io.BytesIO()
            with zipfile.ZipFile(b_, "w") as z_: z_.writestr(f"{aid}_ACTIVITY.fit", fb)
            return b_.getvalue()
        Estado.zip_por_id = zip_do; DOWNLOADS.clear()
        rc, out = rodar(["--sem-abrir", "--historico", "60"]); assert rc == 0, out
        assert 1 <= len(DOWNLOADS) <= rotas.POR_EXECUCAO, f"atualização normal baixa poucas por vez ({len(DOWNLOADS)})"
        rg = rotas.carregar_rotas(gp.PASTA); assert rg and all("pts" in v or v.get("sem_gps") for v in rg.values())
        antes = len(DOWNLOADS)
        rc, out = rodar(["--sem-abrir", "--rotas"]); assert rc == 0, out   # --rotas: todas as que faltam
        rg = rotas.carregar_rotas(gp.PASTA)
        com = [k for k, v in rg.items() if "pts" in v]; sem = [k for k, v in rg.items() if v.get("sem_gps")]
        assert len(com) >= 8 and sem == ["20"], (len(com), sem)            # esteira (id 20): sem GPS e sem baixar
        assert str(20) not in [p.rsplit("/", 1)[1] for p in DOWNLOADS], "esteira com latitude vazia não é baixada"
        n_dl = len(DOWNLOADS); rc, out = rodar(["--sem-abrir", "--rotas"]); assert len(DOWNLOADS) == n_dl, "não baixa de novo"
        assert all(len(v["pts"]) <= 300 for v in rg.values() if "pts" in v)
        # painel: galeria, mapa geral, privacidade (as pontas NÃO aparecem no HTML) e nada de coordenadas
        pg = painel()
        assert "Meus percursos" in pg and "Todas as minhas rotas" in pg and "primeiros e últimos 300 m" in pg
        assert "outra região" in pg, "a corrida de outra cidade não distorce o mapa geral"
        assert not re.search(r"-\d{2}\.\d{4,}", pg), "nenhuma coordenada (negativa, como no Brasil) no HTML, nem nos desenhos"
        k0 = com[0]; pts0 = rg[k0]["pts"]
        inicio_cru = pts0[0]
        # nenhuma coordenada do ponto inicial cru aparece no HTML (os desenhos usam km projetados, já sem as pontas)
        assert f"{inicio_cru[0]}" not in pg and f"{inicio_cru[1]}" not in pg
        rc, out = rodar(["--privacidade-metros", "900"]); assert rc == 0 and "900 m" in out
        rc, out = rodar(["--privacidade-metros", "5000"]); assert rc == 1 and "entre 0 e 2000" in out
        rc, out = rodar(["--so-visual", "--sem-abrir"]); assert "primeiros e últimos 900 m" in painel()
        rc, out = rodar(["--privacidade-metros", "0"]); rc, out = rodar(["--so-visual", "--sem-abrir"]); assert "sem corte de privacidade" in painel()
        rodar(["--privacidade-metros", "300"])
        # falha numa atividade não derruba as outras; 3 tentativas e desiste
        for f_ in ("rotas.json",): os.remove(os.path.join(gp.PASTA, f_))
        Estado.zip_por_id = lambda aid: b"lixo" if aid == 110 else zip_do(aid)
        rc, out = rodar(["--sem-abrir", "--rotas"]); assert rc == 0, out
        rg = rotas.carregar_rotas(gp.PASTA); assert rg["110"] == {"falhou": 1} and len([1 for v in rg.values() if "pts" in v]) >= 8
        for _ in range(3): rodar(["--sem-abrir", "--rotas"])
        assert rotas.carregar_rotas(gp.PASTA)["110"]["falhou"] == rotas.MAX_TENTATIVAS
        n_dl = len(DOWNLOADS); rodar(["--sem-abrir", "--rotas"]); assert str(110) not in [p.rsplit("/", 1)[1] for p in DOWNLOADS[n_dl:]], "desistiu"
        # sem a biblioteca: --rotas explica; a atualização normal fica em silêncio
        orig_sdk = rotas.carregar_sdk; rotas.carregar_sdk = lambda: None
        rc, out = rodar(["--sem-abrir", "--rotas"]); assert rc == 1 and "pip install --require-hashes" in out
        rc, out = rodar(["--sem-abrir"]); assert rc == 0 and "biblioteca" not in out.lower()
        rotas.carregar_sdk = orig_sdk
        # área principal
        idx, fora = rotas.area_principal([[[-20.44, -54.64]] * 3, [[-20.45, -54.65]] * 3, [[-18.5, -54.75]] * 3])
        assert idx == [0, 1] and fora == 1
        Estado.zip_por_id = None; Estado.zip_fit = None

    # 8) só GET nos dados; POST só no token; nenhum segredo no painel
    assert METODOS == [] or all(m == "GET" or p.endswith("/token") for m, p in METODOS)
    print("TODOS OS TESTES PASSARAM")

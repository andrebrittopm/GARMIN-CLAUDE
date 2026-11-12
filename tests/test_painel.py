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
            "respiration": {"avgValue": 14}, "pulseOx": {"avgValue": 95}}

def sono(x):
    i = (HOJE - x).days
    if i in (2, 6, 12): return {"calendarDate": None, "sleepTimeSeconds": None, "deviceRemCapable": False}
    prof, leve, rem = 3600 + i * 120, 14400 + (i * 300) % 3600, 5400 + i * 60
    return {"calendarDate": x.isoformat(), "sleepTimeSeconds": prof + leve + rem,
            "deepSleepSeconds": prof, "lightSleepSeconds": leve, "remSleepSeconds": rem, "deviceRemCapable": True}

ATIV = {1: [("running", 10000, 3000), ("strength_training", None, 2400)], 3: [("cycling", 40000, 5400)],
        4: [("trail_running", 8000, 2800)], 8: [("running", 5000, 1700)], 0: [("lap_swimming", 1500, 2100)],
        6: [("running", 12000, 3900), ("cycling", 20000, 2700)], 11: [("running", 6000, 2000)],
        15: [("running", 7000, 2400)], 22: [("running", 9000, 3000)]}

def ativ_json(i, n, t, dist, dur):
    x = d(i)
    r = {"activityId": i * 10 + n, "startTimeLocal": f"{x.isoformat()} {7 + n * 10:02d}:00:00",
         "activityName": f"Treino <{t}>", "activityType": {"typeKey": t}, "duration": float(dur),
         "averageHR": 150 + i, "elevationGain": 20.0 + i}
    if dist: r.update(distance=float(dist), averageSpeed=dist / dur)
    if "running" in t:
        r.update(averageRunningCadenceInStepsPerMinute=170.0 + n, vO2MaxValue=50.0 + i % 3,
                 hrTimeInZone_1=300.0, hrTimeInZone_2=900.0 + i * 10, hrTimeInZone_3=800.0, hrTimeInZone_4=300.0, hrTimeInZone_5=0.0,
                 fastestSplit_1000=dur / dist * 1000 * 0.93, fastestSplit_5000=dur / dist * 5000 * 0.97 if dist >= 5000 else None)
    return r

class Estado: rejeitar_tokens_velhos = False
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, o, code=200):
        b = json.dumps(o).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        METODOS.append(("POST", self.path))
        if self.headers.get("Authorization") != "ApiKey " + CHAVE_FALSA: return self._json({}, 401)
        self._json({"access_token": TOKEN_FALSO})
    def do_GET(self):
        METODOS.append(("GET", self.path))
        if self.headers.get("Authorization") != "Bearer " + TOKEN_FALSO: return self._json({}, 401)
        u = urllib.parse.urlparse(self.path); q = dict(urllib.parse.parse_qsl(u.query)); p = u.path
        if "dailysummaries" in p: return self._json({"data": [resumo(x) for x in rng(q["startDate"], q["endDate"])]})
        if "dailySleep" in p: return self._json([sono(x) for x in rng(q["startDate"], q["endDate"])])
        if "/hrv-service/hrv/daily/" in p:
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
    for f in ("dados_brutos.json", "painel.html"):
        try: os.remove(os.path.join(gp.PASTA, f))
        except FileNotFoundError: pass

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
    assert "Distância de corrida por semana" in pg and "Tempo por zona" in pg and "Melhores esforços" in pg

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
    f = Falso(); assert len(gp.buscar_atividades(f, d(5), HOJE)) == 45 and f.chamadas == [0, 20, 40]

    # 8) só GET nos dados; POST só no token; nenhum segredo no painel
    assert METODOS == [] or all(m == "GET" or p.endswith("/token") for m, p in METODOS)
    print("TODOS OS TESTES PASSARAM")

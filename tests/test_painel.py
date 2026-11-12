"""Teste com servidor falso: não usa chave nem conta reais.
Gera tests/saida/painel.html (dados inventados SÓ para teste visual)."""
import contextlib, datetime as dt, io, json, os, sys, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import garmin_painel as gp

CHAVE_FALSA = "CHAVE-FALSA-" + "x" * 130
TOKEN_FALSO = "TOKEN-FALSO-abc123"
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
        6: [("running", 12000, 3900), ("cycling", 20000, 2700)], 11: [("running", 6000, 2000)]}

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
            for i, lst in ATIV.items():
                x = d(i)
                if not (q["startDate"] <= x.isoformat() <= q["endDate"]): continue
                for n, (t, dist, dur) in enumerate(lst):
                    r = {"activityId": i * 10 + n, "startTimeLocal": f"{x.isoformat()} {7 + n * 10:02d}:00:00",
                         "activityName": f"Treino <{t}>", "activityType": {"typeKey": t}, "duration": float(dur)}
                    if dist: r.update(distance=float(dist), averageSpeed=dist / dur)
                    out.append(r)
            return self._json(out)
        self._json({}, 404)

srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
gp.BASE = f"http://127.0.0.1:{srv.server_port}"
gp.ler_chave = lambda: CHAVE_FALSA
gp.PASTA = os.path.join(os.path.dirname(__file__), "saida"); os.makedirs(gp.PASTA, exist_ok=True)

def rodar(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rc = gp.main(args)
    return rc, buf.getvalue()

if __name__ == "__main__":
    rc, out = rodar(["--teste", "--data", d(1).isoformat()]); assert rc == 0, out
    assert CHAVE_FALSA not in out and TOKEN_FALSO not in out
    rc, out = rodar(["--sem-abrir"]); print(out); assert rc == 0, out
    pg = open(os.path.join(gp.PASTA, "painel.html"), encoding="utf-8").read()
    assert CHAVE_FALSA not in pg and TOKEN_FALSO not in pg
    assert "Treino &lt;running&gt;" in pg                       # texto escapado
    assert all(m == "GET" or p.endswith("/token") for m, p in METODOS), METODOS
    print("OK; requisições:", sorted(set(m for m, _ in METODOS)))

"""Teste com servidor falso: não usa chave nem conta reais."""
import io, json, os, sys, threading, contextlib, datetime as dt, tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import garmin_painel as gp

CHAVE_FALSA = "CHAVE-FALSA-" + "x" * 130
TOKEN_FALSO = "TOKEN-FALSO-abc123"
METODOS = []

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, o, code=200):
        b = json.dumps(o).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        METODOS.append(("POST", self.path))
        if self.headers.get("Authorization") != "ApiKey " + CHAVE_FALSA: return self._json({}, 401)
        self._json({"access_token": TOKEN_FALSO, "expires_in": 86400})
    def do_GET(self):
        METODOS.append(("GET", self.path))
        if self.headers.get("Authorization") != "Bearer " + TOKEN_FALSO: return self._json({}, 401)
        p = self.path
        hoje = dt.date.today()
        if "dailysummaries" in p:
            return self._json({"data": [{"calendarDate": hoje.isoformat(),
                "movement": {"steps": {"value": 8123}}, "heartRate": {"restingValue": 52, "minValue": 44, "maxValue": 160},
                "stress": {"avgLevel": 31}, "bodyBattery": {"minValue": 20, "maxValue": 90},
                "intensityMinutes": {"moderate": 10, "vigorous": 5}, "calories": {"burnedTotal": 2500}}]})
        if "dailySleep" in p:
            return self._json([{"calendarDate": hoje.isoformat(), "sleepTimeSeconds": 27000}])
        if "activities/search" in p:
            return self._json([
                {"activityId": 1, "startTimeLocal": hoje.isoformat() + " 07:00:00", "activityName": "Corrida <b>",
                 "activityType": {"typeKey": "running"}, "distance": 10000.0, "duration": 3000.0, "averageSpeed": 3.3333},
                {"activityId": 2, "startTimeLocal": hoje.isoformat() + " 18:00:00", "activityName": "Pedal",
                 "activityType": {"typeKey": "cycling"}, "distance": 20000.0, "duration": 3600.0}])
        self._json({}, 404)

srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
gp.BASE = f"http://127.0.0.1:{srv.server_port}"; gp.TOKEN_PATH_URL = None
gp.ler_chave = lambda: CHAVE_FALSA
gp.PASTA = tempfile.mkdtemp()

def rodar(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rc = gp.main(args)
    return rc, buf.getvalue()

rc, out = rodar(["--teste"]); print(out); assert rc == 0
assert CHAVE_FALSA not in out and TOKEN_FALSO not in out
rc, out = rodar(["--sem-abrir"]); print(out); assert rc == 0
pg = open(os.path.join(gp.PASTA, "painel.html"), encoding="utf-8").read()
assert CHAVE_FALSA not in pg and TOKEN_FALSO not in pg
assert "10,00 km" in pg and "5:00 /km" in pg and "8.123" in pg and "7 h 30 min" in pg
assert "Corrida &lt;b&gt;" in pg            # texto escapado
assert "sem dado" in pg                      # campos ausentes
assert all(m == "GET" or p.endswith("/token") for m, p in METODOS), METODOS
assert os.listdir(gp.PASTA) == ["painel.html"]   # só o painel é gravado
print("TODOS OS TESTES PASSARAM; requisições:", sorted(set(m for m, _ in METODOS)))

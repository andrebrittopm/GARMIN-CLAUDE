"""Testes do intervals.icu: servidor falso local, nenhuma chave nem conta reais."""
import base64, contextlib, datetime as dt, io, json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import intervals, cofre, garmin_painel as gp, visual

CHAVE = "CHAVE-INTERVALS-FALSA-123456"
HOJE = dt.date(2026, 11, 12)
VISTOS = []
ESTADO = {"modo": "ok"}
EVENTOS = [
    {"id": 1, "start_date_local": "2026-11-12T00:00:00", "name": "Rodagem <b>leve</b>", "category": "WORKOUT", "type": "Run",
     "moving_time": 2700, "distance": 8000, "description": "SEGREDO-DA-DESCRICAO", "icu_athlete_id": "i99"},
    {"id": 2, "start_date_local": "2026-11-14T00:00:00", "name": "Plantão", "category": "NOTE", "description": "outro segredo"},
    {"id": 3, "start_date_local": "2026-11-30T00:00:00", "name": "Longe", "category": "WORKOUT"},
    {"id": 4, "start_date_local": "lixo", "name": "ruim"}, 5, {"id": 6, "name": "sem data"}]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _r(self, m):
        VISTOS.append((m, self.path, self.headers.get("Authorization")))
        modo = ESTADO["modo"]
        if modo == "401": return self._j(401, {})
        if modo == "404": return self._j(404, {})
        if modo == "302":
            self.send_response(302); self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/outro"); self.end_headers(); return
        if modo == "grande": return self._raw(200, b"[" + b" " * 2_100_000 + b"]")
        if modo == "lixo": return self._raw(200, b"nao e json")
        if modo == "objeto": return self._j(200, {"a": 1})
        self._j(200, EVENTOS)
    def _j(self, c, d): self._raw(c, json.dumps(d).encode())
    def _raw(self, c, b):
        self.send_response(c); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    do_GET = lambda s: s._r("GET")
    do_POST = lambda s: s._r("POST")


srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_port}"

# 1) pedido: só GET, caminho e datas, autenticação Basic API_KEY:chave
ev = intervals.buscar(CHAVE, "0", HOJE, HOJE + dt.timedelta(days=21), BASE)
m, caminho, auth = VISTOS[-1]
assert m == "GET" and caminho == "/api/v1/athlete/0/events?oldest=2026-11-12&newest=2026-12-03", caminho
assert base64.b64decode(auth.split()[1]).decode() == f"API_KEY:{CHAVE}"
assert len(ev) == 6

# 2) normalizar: sem descrição, sem ids, descarta o que não tem data
n = intervals.normalizar(ev)
assert [e["nome"] for e in n] == ["Rodagem <b>leve</b>", "Plantão", "Longe"]
assert n[0] == {"data": "2026-11-12", "nome": "Rodagem <b>leve</b>", "categoria": "Treino", "tipo": "Run", "dur_s": 2700.0, "dist_m": 8000.0}
assert "SEGREDO" not in json.dumps(n) and n[1]["categoria"] == "Anotação" and n[1]["dur_s"] is None

# 3) erros: mensagens seguras, nunca com a chave
for modo, trecho in (("401", "recusou a chave"), ("404", "atleta"), ("302", "302"), ("grande", "maior que o permitido"),
                     ("lixo", "não entendi"), ("objeto", "não entendi")):
    ESTADO["modo"] = modo; VISTOS.clear()
    try: intervals.buscar(CHAVE, "0", HOJE, HOJE, BASE); raise SystemExit("deveria falhar: " + modo)
    except intervals.ErroIntervals as e: assert trecho in str(e) and CHAVE not in str(e), (modo, str(e))
    if modo == "302": assert len(VISTOS) == 1, "redirecionamento não é seguido (a chave não é reenviada)"
ESTADO["modo"] = "ok"
try: intervals.buscar(CHAVE, "0", HOJE, HOJE, "http://exemplo.com"); raise SystemExit("host")
except intervals.ErroIntervals as e: assert "não permitido" in str(e)
try: intervals.buscar(CHAVE, "0", HOJE, HOJE, "https://evil.com"); raise SystemExit("host2")
except intervals.ErroIntervals: pass

with tempfile.TemporaryDirectory() as pasta:
    # 4) atualizar, guardar e ler
    assert intervals.proximos(pasta, HOJE) is None
    agora = dt.datetime(2026, 11, 12, 6, 0)
    assert intervals.atualizar(pasta, CHAVE, HOJE, agora, BASE) == 3
    bruto = open(intervals.caminho(pasta), encoding="utf-8").read()
    assert "SEGREDO" not in bruto and CHAVE not in bruto
    evs, quando = intervals.proximos(pasta, HOJE)
    assert [e["nome"] for e in evs] == ["Rodagem <b>leve</b>", "Plantão"] and quando == "2026-11-12T06:00:00", "só os próximos 14 dias"
    assert intervals.atleta(pasta) == "0" and intervals.definir_atleta(pasta, "I12345") == "i12345" and intervals.atleta(pasta) == "i12345"
    for ruim in ("abc", "i", "../x", "1" * 20):
        try: intervals.definir_atleta(pasta, ruim); raise SystemExit(ruim)
        except ValueError: pass
    assert "/athlete/i12345/events" in (intervals.atualizar(pasta, CHAVE, HOJE, agora, BASE) and VISTOS[-1][1])

    # 5) falha na busca não apaga o que estava guardado; sem chave não faz nada
    antes = open(intervals.caminho(pasta), encoding="utf-8").read()
    ESTADO["modo"] = "401"; VISTOS.clear()
    cofre_antes = cofre.ler_chave_intervals
    gp_ler = lambda: CHAVE
    import cofre as c_; c_.ler_chave_intervals = gp_ler
    orig_atualizar = intervals.atualizar
    intervals.atualizar = lambda p, k, h, a, base=BASE: orig_atualizar(p, k, h, a, BASE)
    av = gp.atualizar_intervals(pasta, HOJE, agora)
    assert av and "recusou" in av[0] and CHAVE not in av[0] and open(intervals.caminho(pasta), encoding="utf-8").read() == antes
    c_.ler_chave_intervals = lambda: None; VISTOS.clear()
    assert gp.atualizar_intervals(pasta, HOJE, agora) == [] and VISTOS == [], "sem chave: nada acontece"
    c_.ler_chave_intervals = cofre_antes; intervals.atualizar = orig_atualizar; ESTADO["modo"] = "ok"

    # 6) cartão na página: texto das mensagens é escapado; dias vazios; aviso de dado velho
    dias = [{"data": (HOJE - dt.timedelta(days=i)).isoformat()} for i in range(30)][::-1]
    for x in dias:
        for k in ("passos", "meta_passos", "sono_s", "sono_prof_s", "sono_leve_s", "sono_rem_s", "fc_repouso", "vfc", "fc_min", "fc_max", "estresse", "bb_min", "bb_max", "intensidade", "calorias", "respiracao", "spo2", "andares", "peso", "hidrat_ml", "meta_hidrat_ml"): x.setdefault(k, None)
    ini = HOJE - dt.timedelta(days=29)
    cal = intervals.proximos(pasta, HOJE)
    pag, _ = visual.pagina(dias, [], ini, HOJE, dt.datetime(2026, 11, 12, 18, 0), calendario=cal)
    assert "Próximos dias" in pag and "Rodagem &lt;b&gt;leve&lt;/b&gt;" in pag and "<b>leve</b>" not in pag
    assert pag.count('class="cal-l') == 14 and pag.count("nada marcado") == 12 and "45 min · 8,00 km" in pag
    assert "Longe" not in pag and "SEGREDO" not in pag
    sem, _ = visual.pagina(dias, [], ini, HOJE, dt.datetime(2026, 11, 12, 18, 0))
    assert "Próximos dias" not in sem, "sem intervals.icu o painel fica igual"
    with open(os.path.join(os.path.dirname(__file__), "saida", "painel_intervals.html"), "w", encoding="utf-8") as f: f.write(pag)

# 7) guardar a chave: valida, grava no cofre, limpa a área de transferência e NUNCA imprime a chave
gravado = {}
orig = (cofre.ler_area_de_transferencia, cofre.gravar_chave_intervals, cofre.limpar_area_de_transferencia)
cofre.gravar_chave_intervals = lambda v: gravado.update(v=v)
limpou = []; cofre.limpar_area_de_transferencia = lambda: limpou.append(1)
# (área de transferência, o que o usuário cola no campo escondido, deve gravar?)
for area, colado, ok in ((CHAVE, None, True), ("", CHAVE, True), ("curta", CHAVE + "\n", True), ("tem espaco no meio 12345", CHAVE, True),
                         ("", "", False), ("", "curta", False), ("", "tem espaco no meio 12345", False), ("", "x" * 300, False),
                         ("lixo", "lixo", False)):
    cofre.ler_area_de_transferencia = lambda t=area: t
    perguntas = []
    def pedir(msg, c=colado): perguntas.append(msg); return c if c is not None else (_ for _ in ()).throw(AssertionError("não deveria pedir"))
    gravado.clear(); limpou.clear(); buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: r = gp.guardar_chave_intervals(pedir)
        except gp.Erro as e: r = str(e)
    assert (gravado.get("v") == CHAVE) is ok and bool(limpou) is ok, (area, colado, r)
    saida_ = buf.getvalue() + str(r) + "".join(perguntas)
    assert CHAVE not in saida_, "a chave nunca é impressa"
    assert bool(perguntas) is (colado is not None), "só pede para colar quando a área de transferência não serve"
    if ok: assert "OK: chave do intervals.icu guardada" in saida_
    else: assert "não parece uma chave" in saida_ and not gravado
cofre.ler_area_de_transferencia, cofre.gravar_chave_intervals, cofre.limpar_area_de_transferencia = orig
srv.shutdown()
print("TESTES DO INTERVALS PASSARAM")

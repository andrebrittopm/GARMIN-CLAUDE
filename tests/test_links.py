"""Links do Strava e do Garmin Connect no topo do painel: validação, perfil, editor e página."""
import datetime as dt, os, re, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import corredor, editor, visual

OK_S = "https://www.strava.com/athletes/12345"
OK_G = "https://connect.garmin.com/modern/profile/abc-123"

# 1) validação: só https do Strava / Garmin Connect
assert corredor.link_valido("strava", OK_S) == OK_S and corredor.link_valido("strava", "https://strava.com/athletes/1") == "https://strava.com/athletes/1"
assert corredor.link_valido("garmin", OK_G) == OK_G and corredor.link_valido("garmin", "  " + OK_G + "  ") == OK_G
ruins = ["", None, "javascript:alert(1)", "data:text/html,x", "http://www.strava.com/athletes/1", "//www.strava.com/athletes/1",
         "https://strava.com.evil.com/athletes/1", "https://evilstrava.com/x", "https://www.strava.com@evil.com/x",
         "https://user:pw@www.strava.com/athletes/1", "https://www.strava.com:8443/x", "https://www.strava.com/a b",
         'https://www.strava.com/x"onclick="y', "https://www.strava.com/<script>", "https://www.strava.com/" + "a" * 400,
         "https://www.strava.com\\@evil.com", "ftp://www.strava.com/x"]
for r in ruins:
    assert corredor.link_valido("strava", r) is None, r
assert corredor.link_valido("garmin", OK_S) is None and corredor.link_valido("strava", OK_G) is None, "cada link só vale para o seu site"
assert corredor.link_valido("outro", OK_S) is None

with tempfile.TemporaryDirectory() as pasta:
    # 2) perfil.txt: aceita os válidos, ignora e avisa os inválidos
    open(os.path.join(pasta, "perfil.txt"), "w", encoding="utf-8").write(f"nome: Eu\nstrava: {OK_S}\ngarmin: https://evil.com/x\n")
    av = []; per = corredor.carregar_perfil(pasta, av)
    assert per["strava"] == OK_S and per["garmin"] == "" and any("link 'garmin' foi ignorado" in a for a in av), av
    open(os.path.join(pasta, "perfil.txt"), "w", encoding="utf-8").write("nome: Eu\n")
    per = corredor.carregar_perfil(pasta, []); assert per["strava"] == per["garmin"] == ""

    # 3) editor: grava, mantém, remove e recusa
    os.makedirs(os.path.join(pasta, "imagens"), exist_ok=True)
    novos = editor.salvar_perfil(pasta, {"nome": "Eu", "strava": OK_S, "garmin": OK_G})
    txt = open(os.path.join(pasta, "perfil.txt"), encoding="utf-8").read()
    assert f"strava: {OK_S}" in txt and f"garmin: {OK_G}" in txt and txt.count("strava:") == 1
    editor.salvar_perfil(pasta, {"nome": "Eu Mudei"}); assert editor.ler_perfil(pasta)[0]["strava"] == OK_S, "campo ausente mantém o link"
    editor.salvar_perfil(pasta, {"nome": "Eu", "strava": ""}); l, _ = editor.ler_perfil(pasta); assert l["strava"] == "" and l["garmin"] == OK_G, "vazio remove"
    antes = open(os.path.join(pasta, "perfil.txt"), encoding="utf-8").read()
    for ruim in ("https://evil.com/x", "javascript:alert(1)", "http://www.strava.com/x"):
        try: editor.salvar_perfil(pasta, {"nome": "Eu", "strava": ruim}); raise SystemExit("deveria recusar " + ruim)
        except editor.ErroEdicao as e: assert "https do próprio Strava" in str(e)
    assert open(os.path.join(pasta, "perfil.txt"), encoding="utf-8").read() == antes, "recusado não altera o arquivo"

# 4) página: botões só com link válido, seguros e escapados
def co(strava, garmin):
    return {"perfil": {"nome": "Eu", "frase": "", "foto_uri": None, "strava": strava, "garmin": garmin},
            "periodo": {"do_ano": True, "desde": dt.date(2026, 1, 1), "dist_m": 1000.0, "n": 1}, "feitas": [], "proximas": []}
h = visual.hero_html(co(OK_S, OK_G), dt.datetime(2026, 11, 12, 10, 0))
assert h.count("hero-link") >= 2 and f'href="{OK_S}"' in h and f'href="{OK_G}"' in h and h.count('rel="noopener noreferrer"') == 2 and 'target="_blank"' in h
assert "tem-links" in h and "Strava" in h and "Garmin Connect" in h
h1 = visual.hero_html(co(OK_S, ""), dt.datetime(2026, 11, 12, 10, 0)); assert h1.count('class="hero-link ') == 1 and "Garmin Connect" not in h1
h0 = visual.hero_html(co("", ""), dt.datetime(2026, 11, 12, 10, 0)); assert 'class="hero-link' not in h0 and "tem-links" not in h0 and "Meus perfis" not in h0
hx = visual.hero_html(co('https://www.strava.com/x"><script>', ""), dt.datetime(2026, 11, 12, 10, 0)); assert "<script>" not in hx.replace("<script>", "", 0) and '"><script>' not in hx
print("TESTES DOS LINKS PASSARAM")

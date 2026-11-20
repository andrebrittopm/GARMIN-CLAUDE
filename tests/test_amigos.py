"""Painel para amigos: a página não pode ter NENHUM dado sensível; o servidor só entrega o link secreto."""
import contextlib, datetime as dt, http.client, io, os, stat, subprocess, sys, tempfile, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import amigos, armazem, garmin_painel as gp, visual

HOJE = dt.date(2026, 11, 12)
RAIZ = os.path.join(os.path.dirname(__file__), "..")
SEGREDOS = {"nome_atividade": "Treino-Secreto-Rua-da-Fazenda", "strava": "https://www.strava.com/athletes/777", "garmin": "https://connect.garmin.com/modern/profile/zzz"}


def ativ(i, dist, dur, nome, tipo="running", **extra):
    x = HOJE - dt.timedelta(days=i)
    r = {"activityId": 5000 + i, "startTimeLocal": f"{x.isoformat()} 07:00:00", "activityName": nome, "activityType": {"typeKey": tipo},
         "duration": float(dur), "distance": float(dist), "averageSpeed": dist / dur, "averageHR": 177, "elevationGain": 33.0,
         "startLatitude": -20.4411, "startLongitude": -54.5611, "vO2MaxValue": 55.0}
    r.update(extra); return r


def dados_falsos():
    d = armazem.vazio()
    for i in range(0, 60):
        k = (HOJE - dt.timedelta(days=i)).isoformat()
        d["resumos"][k] = {"calendarDate": k, "movement": {"steps": {"value": 88888, "goal": 7000}},
                           "heartRate": {"restingValue": 49, "minValue": 41, "maxValue": 166},
                           "bodyBattery": {"minValue": 13, "maxValue": 91}, "pulseOx": {"avgValue": 97}, "stress": {"avgLevel": 23},
                           "hydration": {"consumedInFractionalMl": 1800, "goalInFractionalMl": 2500}}
        d["sonos"][k] = {"calendarDate": k, "sleepTimeSeconds": 27000, "deepSleepSeconds": 5000, "lightSleepSeconds": 15000, "remSleepSeconds": 4000}
        d["vfc"][k] = 68
    d.setdefault("peso", {})[HOJE.isoformat()] = 71.234
    for i, (dist, dur) in enumerate([(10000, 3000), (5000, 1440), (12000, 4000), (21100, 7200)]):
        a = ativ(2 + i * 7, dist, dur, SEGREDOS["nome_atividade"])
        d["atividades"][str(a["activityId"])] = a
    prova = ativ(14, 10000, 2900, "Corrida Teste 10K", eventType={"typeId": 1, "typeKey": "race"})
    d["atividades"][str(prova["activityId"])] = prova
    d.update(ultima_busca="2026-11-12T10:00:00", atualizado_em="2026-11-12T10:00:00", cobertura_ini="2026-01-01")
    return d


with tempfile.TemporaryDirectory() as pasta:
    gp.PASTA_DADOS = pasta
    open(os.path.join(pasta, "perfil.txt"), "w", encoding="utf-8").write(
        f"nome: Ana Corredora\nfrase: Corro por prazer\nstrava: {SEGREDOS['strava']}\ngarmin: {SEGREDOS['garmin']}\n")
    open(os.path.join(pasta, "provas.txt"), "w", encoding="utf-8").write("2027-07-04; Maratona Futura; 10;\n")
    open(os.path.join(pasta, "plano.json"), "w", encoding="utf-8").write(
        '{"prova": {"nome": "Plano Secreto", "data": "2027-07-04", "dist_km": 10, "meta_min": 41.5}, "selos": {"equiv_10k_min": [41.5], "ritmo_s": [249]}}')
    dados = dados_falsos()
    agora = dt.datetime(2026, 11, 12, 18, 0)

    # 1) desligado: nada é publicado
    assert amigos.token(pasta) is None and not amigos.ativo(pasta)
    assert gp.gerar_amigos(dados, HOJE, agora) is False and not os.path.exists(os.path.join(pasta, "publico"))

    # 2) ligar: link secreto forte, só o dono lê; página gerada SEM dados sensíveis
    t = amigos.ligar(pasta); assert len(t) >= 30 and amigos.ligar(pasta) == t, "ligar de novo mantém o link"
    assert stat.S_IMODE(os.stat(os.path.join(pasta, amigos.ARQ_TOKEN)).st_mode) == 0o600
    chamado = []
    visual_rota0 = visual.arte_topo_real; visual.arte_topo_real = lambda *a, **k: chamado.append(1) or ""
    try:
        assert gp.gerar_amigos(dados, HOJE, agora) is True
    finally:
        visual.arte_topo_real = visual_rota0
    assert not chamado, "o desenho do topo não usa rotas reais"
    pag = open(amigos.caminho_pagina(pasta), encoding="utf-8").read()
    for esperado in ("Ana Corredora", "Corro por prazer", "Maratona Futura", "Recordes pessoais", "Conquistas", "Corrida Teste 10K", "Atualizado em 12/11/2026"):
        assert esperado in pag, esperado
    proibido = [SEGREDOS["nome_atividade"], SEGREDOS["strava"], SEGREDOS["garmin"], "strava.com", "garmin.com", "intervals", "88888", "177 bpm", "71,2", "71.234",
                "Sono", "sono", "Body Battery", "VFC", "SpO2", "Hidrata", "Peso", "FC de repouso", "Passos", "Zonas", "Estresse", "Próximos dias",
                "Rumo à prova", "Plano de prova", "Plano Secreto", "Trilha dos ciclos", "41:30", "4:09", "Meus percursos", "Todas as minhas rotas",
                "<script", "data-tip", "/api/", "token", "-20.44", "-54.56", "Atividades", "Dados diários", "Exportar CSV", "EDITOR"]
    achados = [p for p in proibido if p in pag]
    assert not achados, achados
    assert '<meta name="robots" content="noindex,nofollow,noarchive">' in pag and 'class="hero-link' not in pag
    assert "Equivalente abaixo" not in pag and "Ritmo 4:09" not in pag and "Ciclo de" not in pag, "conquistas só as genéricas (sem metas do plano)"

    # 3) o servidor só entrega o link secreto, em GET
    httpd = amigos.criar(pasta, 18866); threading.Thread(target=httpd.serve_forever, daemon=True).start()
    def req(caminho, metodo="GET", host="qualquer.exemplo.com"):
        c = http.client.HTTPConnection("127.0.0.1", 18866, timeout=5)
        c.putrequest(metodo, caminho, skip_host=True); c.putheader("Host", host); c.endheaders()
        r = c.getresponse(); corpo = r.read().decode(); h = dict(r.getheaders()); c.close(); return r.status, corpo, h
    try:
        st, corpo, h = req(f"/{t}/"); assert st == 200 and "Ana Corredora" in corpo
        assert "default-src 'none'" in h["Content-Security-Policy"] and "noindex" in h["X-Robots-Tag"] and h["Referrer-Policy"] == "no-referrer"
        assert h["Cache-Control"] == "no-store" and h["X-Content-Type-Options"] == "nosniff"
        assert req(f"/{t}")[0] == 200
        for ruim in ("/", "/index.html", "/errado", f"/{t}x", f"/{t}/extra", f"/{t[:-1]}", "/" + t.upper(), "/../etc/passwd", f"/{t}/../x", "/api/estado", "/?t=" + t, "/token_amigos.txt", "/publico/index.html", "/painel.html", "/dados_brutos.json"):
            assert req(ruim)[0] == 404, ruim
        assert "Ana" not in req("/")[1]
        for metodo in ("POST", "PUT", "DELETE"):
            assert req(f"/{t}/", metodo)[0] in (501, 405), metodo
        # trocar o link invalida o antigo na hora
        t2 = amigos.novo_link(pasta); assert t2 != t and amigos.token(pasta) == t2
        assert req(f"/{t}/")[0] == 404 and req(f"/{t2}/")[0] == 200
        # desligar: tudo some
        amigos.desligar(pasta); assert not os.path.exists(os.path.join(pasta, amigos.ARQ_TOKEN)) and not os.path.exists(amigos.caminho_pagina(pasta))
        assert req(f"/{t2}/")[0] == 404
    finally:
        httpd.shutdown(); httpd.server_close()

    # 4) linha de comando
    env0 = os.environ.get("PAINEL_HOST"); os.environ["PAINEL_HOST"] = "painel-garmin.tail1234.ts.net"
    try:
        def cmd(*args):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): rc = gp.main(list(args) + ["--pasta-dados", pasta])
            return rc, buf.getvalue()
        rc, out = cmd("--amigos-endereco"); assert rc == 1 and "não está ligado" in out
        rc, out = cmd("--amigos-ligar"); assert rc == 0 and "ligado" in out and amigos.ativo(pasta)
        tok = amigos.token(pasta); rc, out = cmd("--amigos-endereco")
        assert rc == 0 and out.strip() == f"https://painel-garmin.tail1234.ts.net:10000/{tok}/", out
        rc, out = cmd("--amigos-novo-link"); assert rc == 0 and amigos.token(pasta) != tok and tok not in out
        rc, out = cmd("--amigos-desligar"); assert rc == 0 and not amigos.ativo(pasta)
    finally:
        if env0 is None: os.environ.pop("PAINEL_HOST", None)
        else: os.environ["PAINEL_HOST"] = env0

    # 5) sem perfil.txt não publica nada (e avisa)
    amigos.ligar(pasta); os.remove(os.path.join(pasta, "perfil.txt")); buf = io.StringIO()
    with contextlib.redirect_stdout(buf): assert gp.gerar_amigos(dados, HOJE, agora) is False
    assert "precisa do perfil.txt" in buf.getvalue() and not os.path.exists(amigos.caminho_pagina(pasta))

# 5b) modo COMPLETO: o painel inteiro, só para leitura (sem editar, sem atualizar, sem chaves)
import re, shutil
with tempfile.TemporaryDirectory() as pasta:
    gp.PASTA_DADOS = pasta
    open(os.path.join(pasta, "perfil.txt"), "w", encoding="utf-8").write(
        f"nome: Ana Corredora\nstrava: {SEGREDOS['strava']}\ngarmin: {SEGREDOS['garmin']}\n")
    open(os.path.join(pasta, "provas.txt"), "w", encoding="utf-8").write("2027-07-04; Maratona Futura; 10;\n")
    open(os.path.join(pasta, "plano.json"), "w", encoding="utf-8").write(
        '{"prova": {"nome": "Plano Secreto", "data": "2027-07-04", "dist_km": 10, "meta_min": 41.5}, "selos": {"equiv_10k_min": [41.5]}}')
    open(os.path.join(pasta, "config_painel.json"), "w", encoding="utf-8").write('{"chave_vence": "2026-11-17"}')
    dados = dados_falsos(); agora = dt.datetime(2026, 11, 12, 18, 0); ini = HOJE - dt.timedelta(days=29)
    def gerar_tudo():
        with contextlib.redirect_stdout(io.StringIO()): gp.gerar(dados, HOJE, ini, agora, ["aviso interno de teste"], False)
    def publica(): return open(amigos.caminho_pagina(pasta), encoding="utf-8").read()
    amigos.ligar(pasta); assert amigos.modo(pasta) == "basico"
    gerar_tudo(); basico = publica()
    assert not [p_ for p_ in proibido if p_ in basico], "o modo básico continua sem dados sensíveis"
    dono = open(os.path.join(pasta, "painel.html"), encoding="utf-8").read()
    assert 'id="btn-atualizar"' in dono and 'id="btn-editar"' in dono and "<!--EDITOR_CFG-->" in dono, "o SEU painel continua com os botões"
    try: amigos.definir_modo(pasta, "tudo"); raise SystemExit("modo inválido")
    except ValueError: pass
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rc = gp.main(["--amigos-modo", "completo", "--pasta-dados", pasta])
    assert rc == 0 and "ATENÇÃO: modo COMPLETO" in buf.getvalue() and amigos.modo(pasta) == "completo"
    gerar_tudo(); completo = publica()
    for esperado in ("Sono por noite", "Body Battery", "Passos por dia", "Hidratação", "Peso (kg)", "Rumo à prova", "Plano de prova", "Atividades", "Dados diários",
                     SEGREDOS["nome_atividade"], SEGREDOS["strava"], "Ana Corredora", "Maratona Futura", "Organizar", "Tema claro"):
        assert esperado in completo, esperado
    # nada que grave no servidor ou revele quem administra
    for proibido_ro in ('id="btn-atualizar"', 'id="btn-editar"', 'id="editor"', 'id="atu-status"', "window.EDITOR", "<!--EDITOR_CFG-->", "X-Token", "/api/",
                        "Atualizar agora", "Provas e perfil", "fetch(", "XMLHttpRequest", "aviso interno de teste", "vence em", "2026-11-17", "17/11/2026",
                        amigos.token(pasta), "token_painel", "token_amigos"):
        assert proibido_ro not in completo, proibido_ro
    assert '<meta name="robots" content="noindex,nofollow,noarchive">' in completo
    if shutil.which("node"):
        for i, js in enumerate(re.findall(r"<script>(.*?)</script>", completo, re.S)):
            arq = os.path.join(pasta, f"s{i}.js"); open(arq, "w", encoding="utf-8").write(js)
            assert subprocess.run(["node", "--check", arq], capture_output=True).returncode == 0, i
    corpo_vivo = re.sub(r"<template.*?</template>", "", completo, flags=re.S); ids_ = re.findall(r'\bid="([^"]+)"', corpo_vivo)
    assert len(ids_) == len(set(ids_)), "ids únicos também na versão de leitura"
    # servidor: no modo completo a CSP libera só o JavaScript da própria página; no básico continua sem script
    httpd = amigos.criar(pasta, 18867); threading.Thread(target=httpd.serve_forever, daemon=True).start()
    def get(caminho):
        c = http.client.HTTPConnection("127.0.0.1", 18867, timeout=5); c.request("GET", caminho); r = c.getresponse(); b = r.read().decode(); h = dict(r.getheaders()); c.close(); return r.status, b, h
    try:
        tk = amigos.token(pasta); st, corpo, h = get(f"/{tk}/")
        assert st == 200 and "Sono por noite" in corpo and "script-src 'unsafe-inline'" in h["Content-Security-Policy"] and "connect-src" not in h["Content-Security-Policy"]
        assert "default-src 'none'" in h["Content-Security-Policy"] and "img-src data: blob:" in h["Content-Security-Policy"]
        assert get("/api/estado")[0] == 404 and get("/painel.html")[0] == 404
        amigos.definir_modo(pasta, "basico"); assert "script-src" not in get(f"/{tk}/")[2]["Content-Security-Policy"]
    finally:
        httpd.shutdown(); httpd.server_close()
    # voltar ao básico republica a página sem dados sensíveis
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): assert gp.main(["--amigos-modo", "basico", "--pasta-dados", pasta]) == 0
    gerar_tudo(); assert "Sono por noite" not in publica() and not [p_ for p_ in proibido if p_ in publica()]

# 6) arquivos de instalação
D = os.path.join(RAIZ, "deploy")
unit = open(os.path.join(D, "painel-garmin-amigos.service"), encoding="utf-8").read()
for exigido in ("User=painel", "NoNewPrivileges=yes", "ProtectSystem=strict", "--servir-amigos --porta 8766", "MemoryMax="):
    assert exigido in unit, exigido
assert "Credential" not in unit.replace("sem chaves", "") and "User=root" not in unit, "este serviço não recebe chaves"
for f in ("ligar_amigos.sh", "desligar_amigos.sh"):
    arq = os.path.join(D, f); assert os.access(arq, os.X_OK) and subprocess.run(["bash", "-n", arq]).returncode == 0
lig = open(os.path.join(D, "ligar_amigos.sh"), encoding="utf-8").read()
assert "tailscale funnel --bg --https=10000 http://127.0.0.1:8766" in lig and "8443" not in lig.replace("porta 8443", "")
assert "funnel --https=10000 off" in open(os.path.join(D, "desligar_amigos.sh"), encoding="utf-8").read()
assert "painel-garmin-amigos.service" in open(os.path.join(D, "instalar_vps.sh"), encoding="utf-8").read()
print("TESTES DOS AMIGOS PASSARAM")

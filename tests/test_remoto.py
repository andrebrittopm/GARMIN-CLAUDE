"""Modo remoto (VPS atrás do Tailscale): credenciais do systemd, servidor, senha fixa e arquivos de instalação."""
import contextlib, http.client, io, json, os, re, stat, subprocess, sys, tempfile, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cofre, servidor, garmin_painel as gp

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SEGREDO = "SEGREDO-FALSO-DA-CHAVE-123456789"

# 1) credenciais do systemd (Linux): lê o arquivo do serviço; sem ele, erro claro e sem segredo
with tempfile.TemporaryDirectory() as cred:
    open(os.path.join(cred, cofre.NOME_CHAVE), "w").write(SEGREDO + "\n")
    open(os.path.join(cred, cofre.NOME_INTERVALS), "w").write("  chave-intervals-falsa  \n")
    plat, env0 = sys.platform, os.environ.get("CREDENTIALS_DIRECTORY")
    try:
        sys.platform = "linux"; os.environ["CREDENTIALS_DIRECTORY"] = cred
        assert cofre.ler_chave() == SEGREDO and cofre.ler_chave_intervals() == "chave-intervals-falsa"
        assert cofre._credencial_linux("../etc/passwd") is None and cofre._credencial_linux("a/b") is None
        os.environ["CREDENTIALS_DIRECTORY"] = os.path.join(cred, "nao-existe")
        assert cofre.ler_chave_intervals() is None
        try: cofre.ler_chave(); raise SystemExit("deveria falhar sem credencial")
        except cofre.ErroCofre as e: assert "guardar_chave.sh" in str(e) and SEGREDO not in str(e)
        del os.environ["CREDENTIALS_DIRECTORY"]
        try: cofre.ler_chave(); raise SystemExit("sem pasta de credenciais")
        except cofre.ErroCofre: pass
        assert cofre.ler_token_cache() is None, "no Linux o token não é guardado em lugar nenhum"
    finally:
        sys.platform = plat
        if env0 is not None: os.environ["CREDENTIALS_DIRECTORY"] = env0
        else: os.environ.pop("CREDENTIALS_DIRECTORY", None)

with tempfile.TemporaryDirectory() as pasta:
    # 2) senha fixa: criada uma vez, só o dono lê, sobrevive a reinícios, refeita se estragada
    t1 = servidor.token_persistente(pasta); cam = os.path.join(pasta, servidor.ARQ_TOKEN)
    assert len(t1) >= 30 and servidor.token_persistente(pasta) == t1
    assert stat.S_IMODE(os.stat(cam).st_mode) == 0o600
    open(cam, "w").write("curta\n"); t2 = servidor.token_persistente(pasta); assert t2 != "curta" and len(t2) >= 30
    open(cam, "w").write("tem espaco e <html>\n"); assert servidor.token_persistente(pasta) not in ("tem espaco e <html>",)
    token = servidor.token_persistente(pasta)
    open(os.path.join(pasta, "painel.html"), "w", encoding="utf-8").write("<html><!--EDITOR_CFG-->OLA</html>")

    # 3) servidor remoto: Host/Origin do Tailscale aceitos; o resto recusado
    def subir(remoto):
        httpd, tk, porta = servidor.criar(pasta, lambda: None, 0 if False else 18765 if remoto else 18865, token=token, remoto=remoto)
        threading.Thread(target=httpd.serve_forever, daemon=True).start(); return httpd, porta

    def req(porta, caminho, host, origem=None, tok=None):
        c = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
        h = {"Host": host}
        if origem: h["Origin"] = origem
        if tok: h["X-Token"] = tok
        c.putrequest("GET", caminho, skip_host=True, skip_accept_encoding=True)
        for k, v in h.items(): c.putheader(k, v)
        c.endheaders(); r = c.getresponse(); corpo = r.read().decode(); c.close(); return r.status, corpo

    httpd, p = subir(True)
    try:
        TS = "painel-garmin.tail1234.ts.net:8443"
        st, corpo = req(p, f"/?t={token}", TS); assert st == 200 and "OLA" in corpo and token in corpo
        assert req(p, f"/?t={token}", f"127.0.0.1:{p}")[0] == 200, "o próprio endereço local continua valendo"
        assert req(p, "/?t=errada", TS)[0] == 403 and req(p, "/", TS)[0] == 403, "sem a senha certa: negado"
        for host in ("evil.com", "painel.ts.net.evil.com", "painel-garmin.tail1234.ts.net:8443@evil.com", "ts.net", ".ts.net",
                     "x.ts.net:99999999", "painel_garmin.x.ts.net", "127.0.0.1:1", "localhost"):
            assert req(p, f"/?t={token}", host)[0] == 403, host
        assert req(p, "/api/estado", TS, origem="https://painel-garmin.tail1234.ts.net:8443", tok=token)[0] == 200
        assert req(p, "/api/estado", TS, tok=token)[0] == 200
        for org in ("https://evil.com", "http://painel-garmin.tail1234.ts.net:8443", "https://painel.ts.net.evil.com", "null"):
            assert req(p, "/api/estado", TS, origem=org, tok=token)[0] == 403, org
        assert req(p, "/api/estado", TS, tok="errada")[0] == 403
        # mesma porta já em uso: no modo remoto não "foge" para outra (o Tailscale aponta para uma só)
        try: servidor.criar(pasta, lambda: None, p, token=token, remoto=True); raise SystemExit("deveria falhar")
        except OSError as e: assert str(p) in str(e)
    finally:
        httpd.shutdown(); httpd.server_close()
    # fora do modo remoto, o nome do Tailscale NÃO é aceito
    httpd, p = subir(False)
    try:
        assert req(p, f"/?t={token}", f"127.0.0.1:{p}")[0] == 200
        assert req(p, f"/?t={token}", "painel-garmin.tail1234.ts.net:8443")[0] == 403
    finally:
        httpd.shutdown(); httpd.server_close()

    # 4) --endereco: mostra o endereço com a senha (só aqui); sem nome ou sem senha, erro claro
    env0 = {k: os.environ.get(k) for k in ("PAINEL_HOST", "GARMIN_PAINEL_PASTA_DADOS")}
    try:
        os.environ["GARMIN_PAINEL_PASTA_DADOS"] = pasta; os.environ["PAINEL_HOST"] = "painel-garmin.tail1234.ts.net"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = gp.main(["--endereco"])
        assert rc == 0 and buf.getvalue().strip() == f"https://painel-garmin.tail1234.ts.net:8443/?t={token}", buf.getvalue()
        os.remove(os.path.join(pasta, servidor.ARQ_TOKEN)); buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = gp.main(["--endereco"])
        assert rc == 1 and "ainda não foi iniciado" in buf.getvalue()
    finally:
        for k, v in env0.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

# 5) arquivos de instalação: sintaxe, travas de segurança e nenhum segredo
D = os.path.join(RAIZ, "deploy")
for f in ("instalar_vps.sh", "guardar_chave.sh", "rodar.sh", "atualizar_vps.sh"):
    arq = os.path.join(D, f); assert os.access(arq, os.X_OK), f + " precisa ser executável"
    assert subprocess.run(["bash", "-n", arq]).returncode == 0, f
    txt = open(arq, encoding="utf-8").read(); assert txt.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in txt
srv = open(os.path.join(D, "painel-garmin.service"), encoding="utf-8").read()
atu = open(os.path.join(D, "painel-garmin-atualizar.service"), encoding="utf-8").read()
tim = open(os.path.join(D, "painel-garmin-atualizar.timer"), encoding="utf-8").read()
for u in (srv, atu):
    for exigido in ("User=painel", "NoNewPrivileges=yes", "ProtectSystem=strict", "ProtectHome=yes", "PrivateTmp=yes",
                    "ImportCredential=garmin-personal-api-key", "ImportCredential=intervals-icu-api-key", "MemoryMax="):
        assert exigido in u, exigido
    assert "User=root" not in u and "ReadWritePaths=/opt" not in u
assert "--servir --remoto --sem-abrir --porta 8765" in srv and "Restart=on-failure" in srv
assert "Type=oneshot" in atu and "--sem-abrir" in atu and "--servir" not in atu
assert "OnCalendar=" in tim and "Persistent=true" in tim
inst = open(os.path.join(D, "instalar_vps.sh"), encoding="utf-8").read()
assert "tailscale serve --bg --https=8443 http://127.0.0.1:8765" in inst and "chown -R root:root" in inst
assert not re.search(r"systemctl\s+\S+\s+nginx|/etc/nginx|ufw |iptables", inst), "o instalador não toca no nginx nem no firewall"
gk = open(os.path.join(D, "guardar_chave.sh"), encoding="utf-8").read()
assert "read -r -s" in gk and "systemd-creds encrypt" in gk and "printf '%s' \"$K\"" in gk and "echo \"$K\"" not in gk
print("TESTES DO MODO REMOTO PASSARAM")

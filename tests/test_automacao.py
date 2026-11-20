"""Atualização automática da VPS (travas e volta atrás) e a chave de automação limitada. Tudo com falsos locais."""
import importlib.util, json, os, stat, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
RAIZ = os.path.join(os.path.dirname(__file__), "..")
D = os.path.join(RAIZ, "deploy")
os.environ["PAINEL_TESTE"] = "1"

# ---------------------------------------------------------------- A) autoatualizar.py
def carregar(estado):
    os.environ["PAINEL_ESTADO"] = estado
    esp = importlib.util.spec_from_file_location("autoatualizar", os.path.join(D, "autoatualizar.py")); m = importlib.util.module_from_spec(esp); esp.loader.exec_module(m); return m

A, B = "a" * 40, "b" * 40
def runs(*itens): return {"check_runs": [{"name": n, "status": s, "conclusion": c} for n, s, c in itens]}
OK = runs(("Testes (Linux)", "completed", "success"), ("Cofre do Windows (real)", "completed", "failure"))

class Falso:
    """Simula git/systemctl/bash/GitHub; registra o que foi chamado."""
    def __init__(self, head=A, remoto=B, fetch_rc=0, ancestral=True, merge_rc=0, aplicar_rc=0, ativo="active", http=403, ci=OK, ci_erro=False):
        self.__dict__.update(locals()); self.chamadas = []; self.head_atual = head
    def executar(self, args, **kw):
        self.chamadas.append(args); j = " ".join(args)
        if "fetch" in args: return self.fetch_rc, ""
        if "rev-parse" in args: return 0, self.remoto if "FETCH_HEAD" in args else self.head_atual
        if "merge-base" in args: return (0 if self.ancestral else 1), ""
        if "merge" in args: self.head_atual = self.remoto if self.merge_rc == 0 else self.head_atual; return self.merge_rc, ""
        if "reset" in args: self.head_atual = args[-1]; return 0, ""
        if args[0] == "bash": return self.aplicar_rc if self.head_atual == self.remoto else 0, ""
        if args[0] == "systemctl": return 0, self.ativo
        return 0, ""
    def obter_json(self, url):
        assert f"/commits/{self.remoto}/check-runs" in url and url.startswith("https://api.github.com/repos/")
        if self.ci_erro: raise OSError("sem rede")
        return self.ci
    def status_http(self, url): assert url == "http://127.0.0.1:8765/"; return self.http
    def usou(self, trecho): return any(trecho in " ".join(c) for c in self.chamadas)

with tempfile.TemporaryDirectory() as raiz:
    est = os.path.join(raiz, "est.json"); au = carregar(est)
    # a) a trava dos testes
    assert au.ci_aprovado(OK)[0] == "ok" and au.ci_aprovado(runs(("Testes (Linux)", "in_progress", None)))[0] == "pendente"
    assert au.ci_aprovado(runs(("Testes (Linux)", "completed", "failure")))[0] == "falhou" and au.ci_aprovado({"check_runs": []})[0] == "sem-testes"
    assert au.ci_aprovado(runs(("Outro job", "completed", "success")))[0] == "sem-testes", "só vale o job obrigatório"
    assert au.ci_aprovado(runs(("Testes (Linux)", "completed", "cancelled")))[0] == "falhou"
    def rodar(f):
        rc = au.principal(f.executar, f.obter_json, f.status_http, lambda s: None); return rc, json.load(open(est))
    # b) em dia: nada a fazer
    f = Falso(remoto=A); rc, e = rodar(f); assert rc == 0 and e["status"] == "em-dia" and not f.usou("merge --ff-only") and not f.usou("aplicar_vps")
    # c) versão nova + testes aprovados + painel sobe: atualiza
    f = Falso(); rc, e = rodar(f); assert rc == 0 and e["status"] == "atualizado" and f.usou("merge --ff-only FETCH_HEAD") and f.usou("aplicar_vps.sh") and "bbbbbbb" in e["detalhe"]
    # d) testes pendentes/ausentes: espera, sem tocar em nada
    for ci in (runs(("Testes (Linux)", "queued", None)), {"check_runs": []}):
        f = Falso(ci=ci); rc, e = rodar(f); assert rc == 0 and e["status"] == "aguardando-testes" and not f.usou("merge --ff-only") and not f.usou("aplicar_vps")
    # e) testes falharam: não atualiza e sinaliza
    f = Falso(ci=runs(("Testes (Linux)", "completed", "failure"))); rc, e = rodar(f); assert rc == 1 and e["status"] == "testes-falharam" and not f.usou("merge --ff-only")
    # f) sem rede / divergente / merge que falha
    f = Falso(fetch_rc=1); rc, e = rodar(f); assert rc == 1 and e["status"] == "sem-rede" and not f.usou("merge")
    f = Falso(ci_erro=True); rc, e = rodar(f); assert rc == 1 and e["status"] == "sem-rede" and not f.usou("merge --ff-only")
    f = Falso(ancestral=False); rc, e = rodar(f); assert rc == 1 and e["status"] == "divergente" and not f.usou("merge --ff-only") and not f.usou("reset")
    f = Falso(merge_rc=1); rc, e = rodar(f); assert rc == 1 and e["status"] == "erro" and not f.usou("aplicar_vps")
    # g) volta atrás: instalação falhou / painel não subiu / não responde
    for kw, motivo in (({"aplicar_rc": 1}, "instalação"), ({"ativo": "failed"}, "não subiu"), ({"http": None}, "não subiu")):
        f = Falso(**kw); rc, e = rodar(f)
        assert rc == 1 and e["status"] == "voltou-atras" and motivo in e["detalhe"] and f.usou(f"reset --hard {A}") and f.head_atual == A, (kw, e)
    # h) arquivo com defeito de sintaxe: volta atrás (usa uma pasta real com um .py quebrado)
    with tempfile.TemporaryDirectory() as proj:
        os.makedirs(os.path.join(proj, "deploy")); open(os.path.join(proj, "ok.py"), "w").write("x = 1\n"); open(os.path.join(proj, "deploy", "ruim.py"), "w").write("def (:\n")
        assert au.sintaxe_ok(proj) == [os.path.join("deploy", "ruim.py")]
        au.DIR = proj; f = Falso(); rc, e = rodar(f)
        assert rc == 1 and e["status"] == "voltou-atras" and "ruim.py" in e["detalhe"] and f.usou(f"reset --hard {A}") and not f.usou("systemctl")
    assert stat.S_IMODE(os.stat(est).st_mode) == 0o644 and not os.path.exists(est + ".tmp")
    # i) o programa atual da VPS (sintaxe de tudo que será instalado) está válido
    assert au.sintaxe_ok(RAIZ) == [], au.sintaxe_ok(RAIZ)

# ------------------------------------------------------- B) comando_remoto.sh (chave limitada)
with tempfile.TemporaryDirectory() as raiz:
    os.makedirs(os.path.join(raiz, "deploy")); log = os.path.join(raiz, "chamadas.txt")
    for nome in ("rodar.sh", "desligar_amigos.sh"):
        open(os.path.join(raiz, "deploy", nome), "w").write(f'#!/usr/bin/env bash\necho "{nome} $*" >> "{log}"\n'); os.chmod(os.path.join(raiz, "deploy", nome), 0o755)
    open(os.path.join(raiz, "deploy", "autoatualizar.py"), "w").write(f'import sys\nopen(r"{log}", "a").write("autoatualizar " + " ".join(sys.argv[1:]) + "\\n")\n')
    bin_ = os.path.join(raiz, "bin"); os.makedirs(bin_)
    for nome in ("systemctl", "journalctl", "df", "git"):
        open(os.path.join(bin_, nome), "w").write(f'#!/usr/bin/env bash\necho "{nome} $*" >> "{log}"; echo stub-{nome}\n'); os.chmod(os.path.join(bin_, nome), 0o755)
    env0 = dict(os.environ, PAINEL_DIR=raiz, PATH=bin_ + ":" + os.environ["PATH"])
    def pedir(cmd):
        if os.path.exists(log): os.remove(log)
        env = dict(env0)
        if cmd is not None: env["SSH_ORIGINAL_COMMAND"] = cmd
        else: env.pop("SSH_ORIGINAL_COMMAND", None)
        r = subprocess.run(["bash", os.path.join(D, "comando_remoto.sh")], env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr, (open(log).read().strip().splitlines() if os.path.exists(log) else [])
    permitidos = {"diagnostico": ["rodar.sh --diagnostico"], "atualizar-dados": ["rodar.sh --sem-abrir"], "atualizar-dados-rotas": ["rodar.sh --rotas --sem-abrir"],
                  "atualizar-programa": ["autoatualizar --agora"], "amigos-modo basico": ["rodar.sh --amigos-modo basico"],
                  "amigos-modo completo": ["rodar.sh --amigos-modo completo"], "amigos-desligar": ["desligar_amigos.sh"]}
    for cmd, esperado in permitidos.items():
        rc, out, chamadas = pedir(cmd); assert rc == 0 and chamadas == esperado, (cmd, rc, out, chamadas)
    rc, out, ch = pedir("status"); assert rc == 0 and "painel-garmin.service: stub-systemctl" in out and "stub-df" in out
    rc, out, ch = pedir("logs"); assert rc == 0 and any("journalctl" in c for c in ch)
    negados = [None, "", "ls", "bash", "sh -c id", "cat /etc/shadow", "status; id", "status && id", "status | cat", "status `id`", "status $(id)", "status\nid", "status\n", "Status",
               "diagnostico --ajuda", "diagnostico extra", "atualizar-dados --rotas", "amigos-modo tudo", "amigos-modo basico extra", "amigos-modo", "amigos-endereco",
               "amigos-novo-link", "amigos-ligar", "rodar.sh --amigos-endereco", "../../etc/passwd", "scp -t /tmp", "sftp", "-oProxyCommand=x", "a" * 80,
               "enviar-chave garmin", "guardar-chave garmin", "token", "env", "printenv", "cat /var/lib/painel-garmin/token_painel.txt", "rodar.sh --endereco"]
    for cmd in negados:
        rc, out, ch = pedir(cmd); assert rc == 126 and "NEGADO" in out and ch == [], (repr(cmd), rc, out, ch)

# ------------------------------------------------------- C) instalar/remover a chave limitada
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKRo+QDAYjSKVi2Id+hlQ7Jg7yg/ilg8NLjB5sx5xQxp painel-automacao"
with tempfile.TemporaryDirectory() as raiz:
    auth = os.path.join(raiz, "ssh", "authorized_keys"); os.makedirs(os.path.dirname(auth))
    open(auth, "w").write("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOUTRAchaveDoDonoDaVps1234567890abcdef dono\n")
    env = dict(os.environ, PAINEL_AUTHORIZED=auth, PAINEL_COMANDO="/opt/painel-garmin/deploy/comando_remoto.sh")
    def inst(entrada):
        r = subprocess.run(["bash", os.path.join(D, "instalar_chave_automacao.sh")], input=entrada, env=env, capture_output=True, text=True); return r.returncode, r.stdout + r.stderr
    rc, out = inst(PUB + "\r\n"); assert rc == 0 and "OK" in out
    linhas = open(auth).read().splitlines(); assert len(linhas) == 2 and linhas[0].endswith(" dono"), "a chave do dono é preservada"
    assert linhas[1] == 'command="/opt/painel-garmin/deploy/comando_remoto.sh",restrict ' + PUB.rsplit(" ", 1)[0] + " painel-automacao"
    assert stat.S_IMODE(os.stat(auth).st_mode) == 0o600
    rc, out = inst(PUB); assert rc == 1 and "já está autorizada" in out and len(open(auth).read().splitlines()) == 2, "não duplica"
    for ruim in ("", "ssh-rsa AAAAB3NzaC1yc2E", "ssh-ed25519 curta", PUB + "\nssh-ed25519 AAAAxxxxxxxxxxxxxxxxxxxxxxxx outra", 'command="rm -rf /" ' + PUB,
                 "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKRo+QDAYjSKVi2Id+hlQ7Jg7yg/ilg8NLjB5sx5xQxp x;rm -rf /"):
        antes = open(auth).read(); rc, out = inst(ruim)
        assert rc == 1 and open(auth).read() == antes, repr(ruim)
    r = subprocess.run(["bash", os.path.join(D, "remover_chave_automacao.sh")], env=env, capture_output=True, text=True)
    assert r.returncode == 0 and "Removidas: 1" in r.stdout and open(auth).read().splitlines()[0].endswith(" dono") and len(open(auth).read().splitlines()) == 1

# ------------------------------------------------------- D) arquivos
for f in ("autoatualizar.py", "aplicar_vps.sh", "atualizar_vps.sh", "comando_remoto.sh", "instalar_chave_automacao.sh", "remover_chave_automacao.sh",
          "ligar_autoatualizacao.sh", "desligar_autoatualizacao.sh"):
    assert os.access(os.path.join(D, f), os.X_OK), f
    if f.endswith(".sh"): assert subprocess.run(["bash", "-n", os.path.join(D, f)]).returncode == 0, f
tim = open(os.path.join(D, "painel-garmin-autoatualizar.timer"), encoding="utf-8").read()
assert "OnCalendar=*-*-* 03:40,15:40" in tim and "Persistent=true" in tim
srv = open(os.path.join(D, "painel-garmin-autoatualizar.service"), encoding="utf-8").read()
assert "Type=oneshot" in srv and "deploy/autoatualizar.py" in srv
apl = open(os.path.join(D, "aplicar_vps.sh"), encoding="utf-8").read()
assert "painel-garmin-autoatualizar.timer" in apl and "ligar_credenciais.sh" in apl and "git " not in apl.replace("# ", ""), "aplicar não baixa nada"
atu = open(os.path.join(D, "atualizar_vps.sh"), encoding="utf-8").read()
assert "fetch" in atu and "merge --ff-only" in atu and "aplicar_vps.sh" in atu
cr = open(os.path.join(D, "comando_remoto.sh"), encoding="utf-8").read()
assert "eval" not in cr and "bash -c" not in cr and "$CMD" in cr and cr.count("exec ") == 7
print("TESTES DA AUTOMAÇÃO PASSARAM")

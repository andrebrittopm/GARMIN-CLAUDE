#!/usr/bin/env python3
"""Atualiza o PROGRAMA da VPS a partir do GitHub, com travas. Rodado como root pelo agendador (2x por dia).

Só atualiza se TODAS estas condições valerem:
  1. há uma versão nova no ramo configurado e ela só avança o que já está instalado (fast-forward);
  2. os testes automáticos do GitHub dessa versão ("Testes (Linux)") terminaram e PASSARAM;
  3. todos os arquivos .py da versão nova têm sintaxe válida;
  4. depois de aplicar, o painel sobe e responde. Senão, volta sozinho para a versão anterior.
O resultado fica em /var/lib/painel-garmin/autoatualizacao.json (o --diagnostico mostra).
Seus dados e suas chaves nunca são tocados. Para desligar: deploy/desligar_autoatualizacao.sh
Uso: autoatualizar.py [--agora]   (--agora = mesma coisa, pedida manualmente)
"""
import ast
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

DIR = os.environ.get("PAINEL_DIR", "/opt/painel-garmin")
REPO = "andrebrittopm/GARMIN-CLAUDE"
RAMO = "claude/garmin-data-dashboard-fi7vqq"
JOB_OBRIGATORIO = "Testes (Linux)"
ESTADO = os.environ.get("PAINEL_ESTADO", "/var/lib/painel-garmin/autoatualizacao.json")
GIT = ["git", "-c", f"safe.directory={DIR}", "-C", DIR]


def sh(args, **kw):
    """Roda um comando e devolve (código, saída). Nunca levanta erro por falha do comando."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=kw.pop("timeout", 300),
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), **kw)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return 127, type(e).__name__


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "painel-pessoal/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read(2_000_000))


def http_status(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code              # 403 também prova que o servidor respondeu
    except (urllib.error.URLError, OSError):
        return None


def ci_aprovado(dados):
    """(estado, detalhe): 'ok', 'pendente', 'falhou' ou 'sem-testes', a partir da resposta check-runs do GitHub."""
    runs = [r for r in (dados.get("check_runs") or []) if r.get("name") == JOB_OBRIGATORIO]
    if not runs:
        return "sem-testes", "o GitHub ainda não tem o resultado dos testes desta versão"
    if any(r.get("status") != "completed" for r in runs):
        return "pendente", "os testes ainda estão rodando"
    if all(r.get("conclusion") == "success" for r in runs):
        return "ok", ""
    return "falhou", "os testes automáticos do GitHub falharam"


def sintaxe_ok(pasta):
    """Todos os .py da pasta (raiz e deploy/) com sintaxe válida. Devolve a lista de arquivos com defeito."""
    ruins = []
    for sub in ("", "deploy"):
        base = os.path.join(pasta, sub)
        for nome in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            if nome.endswith(".py"):
                try:
                    with open(os.path.join(base, nome), "rb") as f:
                        ast.parse(f.read(), nome)
                except (SyntaxError, ValueError):
                    ruins.append(os.path.join(sub, nome))
    return ruins


def gravar_estado(status, detalhe="", sha=""):
    d = {"status": status, "detalhe": detalhe, "sha": sha[:12], "em": dt.datetime.now().isoformat(timespec="seconds")}
    try:
        os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
        tmp = ESTADO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.chmod(tmp, 0o644)
        os.replace(tmp, ESTADO)
    except OSError:
        pass
    print(f"[autoatualizar] {status}" + (f": {detalhe}" if detalhe else "") + (f" ({sha[:7]})" if sha else ""), flush=True)


def principal(executar=sh, obter_json=http_json, status_http=http_status, esperar=time.sleep):
    rc, saida = executar(GIT + ["fetch", "--quiet", "origin", RAMO])
    if rc != 0:
        gravar_estado("sem-rede", "não consegui falar com o GitHub")
        return 1
    _, novo = executar(GIT + ["rev-parse", "FETCH_HEAD"])
    _, atual = executar(GIT + ["rev-parse", "HEAD"])
    if not re.fullmatch(r"[0-9a-f]{40}", novo or "") or not re.fullmatch(r"[0-9a-f]{40}", atual or ""):
        gravar_estado("erro", "não consegui ler as versões do git")
        return 1
    if novo == atual:
        gravar_estado("em-dia", "", atual)
        return 0
    if executar(GIT + ["merge-base", "--is-ancestor", atual, novo])[0] != 0:
        gravar_estado("divergente", "a versão do GitHub não continua a instalada; nada foi alterado", atual)
        return 1
    try:
        estado, detalhe = ci_aprovado(obter_json(f"https://api.github.com/repos/{REPO}/commits/{novo}/check-runs?per_page=50"))
    except (urllib.error.URLError, OSError, ValueError):
        gravar_estado("sem-rede", "não consegui consultar os testes no GitHub", atual)
        return 1
    if estado != "ok":
        gravar_estado("aguardando-testes" if estado in ("pendente", "sem-testes") else "testes-falharam", detalhe, novo)
        return 0 if estado in ("pendente", "sem-testes") else 1
    if executar(GIT + ["merge", "--ff-only", "FETCH_HEAD"])[0] != 0:
        gravar_estado("erro", "não consegui aplicar a versão nova; nada foi alterado", atual)
        return 1

    def voltar(motivo):
        executar(GIT + ["reset", "--hard", atual])
        executar(["bash", os.path.join(DIR, "deploy", "aplicar_vps.sh")])
        gravar_estado("voltou-atras", motivo, novo)
        return 1

    ruins = sintaxe_ok(DIR)
    if ruins:
        return voltar("arquivo com defeito: " + ", ".join(ruins[:3]))
    rc, saida = executar(["bash", os.path.join(DIR, "deploy", "aplicar_vps.sh")])
    if rc != 0:
        return voltar("a instalação da versão nova falhou")
    esperar(8)
    ativo = executar(["systemctl", "is-active", "painel-garmin.service"])[1].strip() == "active"
    if not ativo or status_http("http://127.0.0.1:8765/") is None:
        return voltar("o painel não subiu com a versão nova")
    gravar_estado("atualizado", f"de {atual[:7]} para {novo[:7]}", novo)
    return 0


if __name__ == "__main__":
    if os.geteuid() != 0 and not os.environ.get("PAINEL_TESTE"):
        print("ERRO: rode como root.", file=sys.stderr)
        sys.exit(1)
    sys.exit(principal())

"""Atualiza o PROGRAMA (não os seus dados) a partir do seu repositório no GitHub.

Como funciona: pergunta ao GitHub qual é a versão mais recente do ramo, baixa essa
versão (fixada pelo código dela, o "sha"), mostra o que vai mudar e, depois do seu OK,
troca os arquivos do programa. Cada .py novo é conferido (sintaxe) antes de qualquer
troca; a versão antiga fica guardada em backup_programa/ e pode ser restaurada.

Segurança:
- só fala com api.github.com e codeload.github.com, por HTTPS verificado;
- só troca arquivos da LISTA PERMITIDA na pasta do programa (.py, .bat, GUIA.md,
  LEIA-ME.md, requirements-fit.txt). Nunca toca em perfil.txt, provas.txt, imagens,
  dados_brutos.json, rotas.json, config, backups, libs;
- ignora qualquer caminho dentro do ZIP (pastas, "..", barras);
- limites de tamanho; nada é executado durante a atualização.
IMPORTANTE: o programa novo roda no seu computador com acesso à sua chave da Garmin.
Mantenha a verificação em duas etapas ligada na sua conta do GitHub.
"""
import datetime as dt
import io
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile
from urllib.parse import urlparse

REPO = "andrebrittopm/GARMIN-CLAUDE"
RAMO = "claude/garmin-data-dashboard-fi7vqq"
API = "https://api.github.com"
CODELOAD = "https://codeload.github.com"
HOSTS_OK = {"api.github.com", "codeload.github.com"}
PADROES = [r"[a-z_]+\.py", r"[a-z_]+\.bat", r"GUIA\.md", r"LEIA-ME\.md", r"requirements-fit\.txt"]
LIMITE_ZIP = 15_000_000
LIMITE_ARQ = 2_000_000
PASTA_PROGRAMA = os.path.dirname(os.path.abspath(__file__))
UA = "painel-pessoal/1.0"


class ErroAtualizador(Exception):
    """Mensagem segura para mostrar ao usuário."""


def _baixar(url, limite, aceitar):
    host = urlparse(url).hostname
    if host not in HOSTS_OK:
        raise ErroAtualizador("Endereço de atualização não permitido.")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": aceitar})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            dados = r.read(limite + 1)
    except urllib.error.HTTPError as e:
        raise ErroAtualizador(f"O GitHub respondeu {e.code}"
                              + (" (repositório ou ramo não encontrado, ou limite de pedidos)"
                                 if e.code in (403, 404) else "") + ".") from None
    except urllib.error.URLError as e:
        raise ErroAtualizador(f"Sem conexão com o GitHub ({type(e.reason).__name__}).") from None
    if len(dados) > limite:
        raise ErroAtualizador("A resposta do GitHub é maior que o permitido.")
    return dados


def ultimo_commit(repo=REPO, ramo=RAMO):
    """(sha, data, primeira linha da mensagem) do commit mais recente do ramo."""
    d = json.loads(_baixar(f"{API}/repos/{repo}/commits/{ramo}", 200_000, "application/vnd.github+json"))
    sha = str(d.get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ErroAtualizador("O GitHub não informou a versão mais recente.")
    c = d.get("commit") or {}
    data = ((c.get("committer") or {}).get("date") or "")[:10]
    msg = str(c.get("message") or "").split("\n")[0][:120]
    return sha, data, msg


def arquivos_do_zip(zip_bytes):
    """{nome: bytes} só dos arquivos permitidos, na raiz do projeto."""
    out = {}
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise ErroAtualizador("O arquivo baixado não é um ZIP válido.") from None
    for info in z.infolist():
        if info.is_dir():
            continue
        partes = info.filename.replace("\\", "/").split("/")
        if len(partes) != 2:           # raiz-do-zip/arquivo: nada de subpastas
            continue
        nome = partes[1]
        if not any(re.fullmatch(p, nome) for p in PADROES):
            continue
        if info.file_size > LIMITE_ARQ:
            raise ErroAtualizador(f"O arquivo {nome} é grande demais.")
        out[nome] = z.read(info)
    if "garmin_painel.py" not in out:
        raise ErroAtualizador("A versão baixada não tem o garmin_painel.py; nada foi alterado.")
    return out


def conferir_sintaxe(arquivos):
    """Levanta erro se algum .py novo tiver defeito de sintaxe (antes de trocar qualquer coisa)."""
    for nome, dados in arquivos.items():
        if nome.endswith(".py"):
            try:
                compile(dados, nome, "exec")
            except (SyntaxError, ValueError):
                raise ErroAtualizador(f"O arquivo novo {nome} está com defeito; nada foi alterado.") from None


def comparar(arquivos, pasta):
    """Lista (nome, status): 'novo', 'alterado' ou 'igual'."""
    out = []
    for nome in sorted(arquivos):
        cam = os.path.join(pasta, nome)
        if not os.path.exists(cam):
            out.append((nome, "novo"))
        else:
            with open(cam, "rb") as f:
                out.append((nome, "igual" if f.read() == arquivos[nome] else "alterado"))
    return out


def aplicar(pasta, arquivos, mudancas, sha, data, msg, agora=None):
    """Guarda a versão antiga e grava a nova. Devolve a pasta de backup."""
    agora = agora or dt.datetime.now()
    mudar = [n for n, s in mudancas if s != "igual"]
    bkp = os.path.join(pasta, "backup_programa", agora.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(bkp, exist_ok=True)
    for nome in mudar:
        cam = os.path.join(pasta, nome)
        if os.path.exists(cam):
            shutil.copy2(cam, os.path.join(bkp, nome))
    vers = os.path.join(pasta, "versao.txt")
    if os.path.exists(vers):
        shutil.copy2(vers, os.path.join(bkp, "versao.txt"))
    for nome in mudar:
        tmp = os.path.join(pasta, nome + ".novo")
        with open(tmp, "wb") as f:
            f.write(arquivos[nome])
        os.replace(tmp, os.path.join(pasta, nome))
    with open(vers, "w", encoding="utf-8") as f:
        json.dump({"sha": sha, "data": data, "mensagem": msg, "aplicado_em": agora.isoformat(timespec="seconds"),
                   "arquivos": mudar}, f, ensure_ascii=False, indent=1)
    # guarda só as 5 cópias mais recentes
    velhos = sorted(d for d in os.listdir(os.path.join(pasta, "backup_programa")))[:-5]
    for v in velhos:
        shutil.rmtree(os.path.join(pasta, "backup_programa", v), ignore_errors=True)
    return bkp


def versao_atual(pasta=PASTA_PROGRAMA):
    try:
        with open(os.path.join(pasta, "versao.txt"), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def desfazer(pasta=PASTA_PROGRAMA, log=print):
    """Volta ao estado anterior: restaura o que foi trocado e remove o que a atualização criou."""
    base = os.path.join(pasta, "backup_programa")
    if not os.path.isdir(base) or not os.listdir(base):
        raise ErroAtualizador("Não há cópia anterior para restaurar.")
    ultimo = sorted(os.listdir(base))[-1]
    pasta_b = os.path.join(base, ultimo)
    guardados = {n for n in os.listdir(pasta_b) if any(re.fullmatch(p, n) for p in PADROES)}
    atual = versao_atual(pasta) or {}
    for nome in atual.get("arquivos", []):                    # criados pela atualização
        if nome not in guardados and any(re.fullmatch(p, nome) for p in PADROES):
            try:
                os.remove(os.path.join(pasta, nome))
                log(f"  removido (era novo): {nome}")
            except OSError:
                pass
    for nome in sorted(guardados):
        shutil.copy2(os.path.join(pasta_b, nome), os.path.join(pasta, nome + ".novo"))
        os.replace(os.path.join(pasta, nome + ".novo"), os.path.join(pasta, nome))
        log(f"  restaurado: {nome}")
    vers = os.path.join(pasta, "versao.txt")
    if os.path.exists(os.path.join(pasta_b, "versao.txt")):
        shutil.copy2(os.path.join(pasta_b, "versao.txt"), vers)
    elif os.path.exists(vers):
        os.remove(vers)
    shutil.rmtree(pasta_b, ignore_errors=True)
    log("Versão anterior restaurada.")


def executar(pasta=PASTA_PROGRAMA, simular=False, perguntar=True, repo=REPO, ramo=RAMO,
             entrada=input, log=print):
    sha, data, msg = ultimo_commit(repo, ramo)
    atual = versao_atual(pasta)
    log(f"Versão mais recente: {sha[:7]} ({data}) {msg}")
    if atual and atual.get("sha") == sha:
        log("O programa já está nessa versão. Nada a fazer.")
        return 0
    arquivos = arquivos_do_zip(_baixar(f"{CODELOAD}/{repo}/zip/{sha}", LIMITE_ZIP, "application/zip"))
    conferir_sintaxe(arquivos)
    mudancas = comparar(arquivos, pasta)
    alvo = [(n, s) for n, s in mudancas if s != "igual"]
    if not alvo:
        log("Os arquivos já são idênticos aos da versão mais recente.")
        if not simular:
            aplicar(pasta, arquivos, mudancas, sha, data, msg)
        return 0
    log("O que vai mudar:")
    for n, s in alvo:
        log(f"  {s:9s} {n}")
    log("Seus dados, fotos, logos, provas e a biblioteca da Garmin não serão tocados.")
    if simular:
        log("(simulação: nada foi alterado)")
        return 0
    if perguntar and entrada("Aplicar a atualização? [S/n] ").strip().lower() in ("n", "nao", "não"):
        log("Cancelado. Nada foi alterado.")
        return 0
    bkp = aplicar(pasta, arquivos, mudancas, sha, data, msg)
    log(f"Pronto! {len(alvo)} arquivo(s) atualizado(s). Cópia da versão anterior: {os.path.basename(bkp)} "
        "(para voltar: --desfazer-atualizacao).")
    return 0

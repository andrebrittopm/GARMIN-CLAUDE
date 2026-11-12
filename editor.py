"""Edição de provas e perfil (lógica, sem rede): lê e grava provas.txt, perfil.txt e imagens.

Regras de segurança:
- só escreve em provas.txt, perfil.txt, imagens/corridas/ e imagens/ (a foto);
- nomes de arquivo de imagem são GERADOS aqui (nunca vêm do formulário);
- imagem só se o conteúdo bate com o tipo (png, jpg, webp, gif, svg) e tem até 2,5 MB;
- linhas de comentário e linhas que não entendemos são preservadas ao regravar;
- cada alteração confere a "versão" do arquivo: se ele mudou por fora, recusa (sem sobrescrever).
"""
import base64
import binascii
import datetime as dt
import hashlib
import os
import re
import secrets
import unicodedata

import corredor

LIMITE_IMG = corredor.LIMITE_BYTES
EXT_OK = {"png": ".png", "jpg": ".jpg", "jpeg": ".jpg", "webp": ".webp", "gif": ".gif", "svg": ".svg"}
CABECALHO_PROVAS = corredor.MODELO_PROVAS


class ErroEdicao(Exception):
    """Mensagem para mostrar ao usuário (sem segredos)."""

    def __init__(self, msg, codigo=400):
        super().__init__(msg)
        self.codigo = codigo


# ------------------------------------------------------------------ arquivos --
def _ler(caminho):
    try:
        with open(caminho, encoding="utf-8-sig", newline="") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _gravar(caminho, texto):
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(texto)
    os.replace(tmp, caminho)


def versao(texto):
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]


def _linhas(texto):
    return texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")


# --------------------------------------------------------------------- provas --
def _parse_linha(linha):
    """dict da prova, ou None se a linha é comentário/vazia/inválida."""
    s = linha.strip()
    if not s or s.startswith("#"):
        return None
    p = [x.strip() for x in s.split(";")]
    if len(p) < 2 or not p[1]:
        return None
    try:
        data = corredor._data(p[0])
    except ValueError:
        return None
    dist = None
    if len(p) > 2 and p[2]:
        try:
            dist = float(p[2].lower().replace("km", "").replace(",", ".").strip())
        except ValueError:
            dist = None
    return {"data": data.isoformat(), "nome": p[1], "dist_km": dist, "logo": (p[3] if len(p) > 3 else "") or ""}


def listar_provas(pasta):
    """(lista de provas com 'id' = número da linha, versão do arquivo)."""
    texto = _ler(os.path.join(pasta, "provas.txt"))
    out = []
    for n, linha in enumerate(_linhas(texto), 1):
        p = _parse_linha(linha)
        if p:
            p["id"] = n
            out.append(p)
    return sorted(out, key=lambda x: x["data"]), versao(texto)


def _formatar(p):
    """Linha do provas.txt: data; nome; distância; logo (sem ; sobrando no fim)."""
    dist = ""
    if p.get("dist_km"):
        d = float(p["dist_km"])
        dist = str(int(d)) if d == int(d) else str(d).replace(".", ",")
    partes = [p["data"], p["nome"], dist]
    if p.get("logo"):
        partes.append(p["logo"])
    return "; ".join(partes).rstrip("; ").rstrip()


def validar_prova(d):
    """Normaliza e valida os campos vindos do formulário."""
    nome = " ".join(str(d.get("nome") or "").split())
    if not nome:
        raise ErroEdicao("Informe o nome da prova.")
    if len(nome) > 120:
        raise ErroEdicao("O nome da prova é longo demais (máximo 120 caracteres).")
    nome = nome.replace(";", ",")
    try:
        data = dt.date.fromisoformat(str(d.get("data") or ""))
    except ValueError:
        raise ErroEdicao("Informe uma data válida.") from None
    if not dt.date(1990, 1, 1) <= data <= dt.date(2100, 12, 31):
        raise ErroEdicao("A data está fora do intervalo aceito.")
    dist = d.get("dist_km")
    if dist in (None, ""):
        dist = None
    else:
        try:
            dist = float(str(dist).replace(",", "."))
        except ValueError:
            raise ErroEdicao("A distância deve ser um número (ex.: 10 ou 21,1).") from None
        if not 0 < dist < 1000:
            raise ErroEdicao("A distância deve ser maior que 0 e menor que 1000 km.")
    return {"data": data.isoformat(), "nome": nome, "dist_km": dist}


def _slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return (t or "prova")[:30]


def salvar_imagem(pasta_destino, base_nome, ext, b64):
    """Grava a imagem enviada com um nome gerado e devolve o nome do arquivo."""
    ext = EXT_OK.get(str(ext or "").lower().lstrip("."))
    if not ext:
        raise ErroEdicao("Tipo de imagem não aceito. Use png, jpg, webp, gif ou svg.")
    try:
        dados = base64.b64decode(str(b64 or ""), validate=True)
    except (binascii.Error, ValueError):
        raise ErroEdicao("A imagem veio corrompida. Tente escolher o arquivo de novo.") from None
    if not dados:
        raise ErroEdicao("A imagem está vazia.")
    if len(dados) > LIMITE_IMG:
        raise ErroEdicao(f"A imagem tem mais de {LIMITE_IMG // 1_000_000} MB. Reduza-a e tente de novo.")
    if not corredor._bytes_ok(ext, dados):
        raise ErroEdicao(f"O arquivo não parece ser uma imagem {ext[1:]} de verdade.")
    os.makedirs(pasta_destino, exist_ok=True)
    nome = f"{_slug(base_nome)}-{secrets.token_hex(3)}{ext}"
    with open(os.path.join(pasta_destino, nome), "wb") as f:
        f.write(dados)
    return nome


def _apagar_logo_se_sem_uso(pasta, nome, linhas_restantes):
    """Remove o arquivo de logo se nenhuma outra prova usa e se ele é um que NÓS criamos."""
    if not nome or not re.fullmatch(r"[a-z0-9-]{1,30}-[0-9a-f]{6}\.(png|jpg|webp|gif|svg)", nome):
        return
    if any(((_parse_linha(x) or {}).get("logo") == nome) for x in linhas_restantes):
        return
    try:
        os.remove(os.path.join(pasta, "imagens", "corridas", nome))
    except OSError:
        pass


def _checar_versao(texto, v):
    if v is not None and versao(texto) != v:
        raise ErroEdicao("O arquivo provas.txt mudou fora do painel. Recarregue a página e tente de novo.", 409)


def adicionar_prova(pasta, d, v_arquivo=None):
    prova = validar_prova(d)
    cam = os.path.join(pasta, "provas.txt")
    texto = _ler(cam)
    if os.path.exists(cam):
        _checar_versao(texto, v_arquivo)
    texto = texto or CABECALHO_PROVAS
    if d.get("logo_b64"):
        prova["logo"] = salvar_imagem(os.path.join(pasta, "imagens", "corridas"), prova["nome"], d.get("logo_ext"), d["logo_b64"])
    linhas = _linhas(texto)
    while linhas and linhas[-1] == "":
        linhas.pop()
    linhas.append(_formatar(prova))
    _gravar(cam, "\n".join(linhas) + "\n")
    return prova


def editar_prova(pasta, pid, d, v_arquivo=None):
    cam = os.path.join(pasta, "provas.txt")
    texto = _ler(cam)
    _checar_versao(texto, v_arquivo)
    linhas = _linhas(texto)
    if not isinstance(pid, int) or not 1 <= pid <= len(linhas) or not _parse_linha(linhas[pid - 1]):
        raise ErroEdicao("Essa prova não existe mais. Recarregue a página.", 404)
    antiga = _parse_linha(linhas[pid - 1])
    prova = validar_prova({**{"data": antiga["data"], "nome": antiga["nome"], "dist_km": antiga["dist_km"]}, **d})
    prova["logo"] = antiga["logo"]
    if d.get("logo_b64"):
        prova["logo"] = salvar_imagem(os.path.join(pasta, "imagens", "corridas"), prova["nome"], d.get("logo_ext"), d["logo_b64"])
    elif d.get("remover_logo"):
        prova["logo"] = ""
    linhas[pid - 1] = _formatar(prova)
    _gravar(cam, "\n".join(linhas))
    if antiga["logo"] and antiga["logo"] != prova["logo"]:
        _apagar_logo_se_sem_uso(pasta, antiga["logo"], linhas)
    return prova


def apagar_prova(pasta, pid, v_arquivo=None):
    cam = os.path.join(pasta, "provas.txt")
    texto = _ler(cam)
    _checar_versao(texto, v_arquivo)
    linhas = _linhas(texto)
    if not isinstance(pid, int) or not 1 <= pid <= len(linhas) or not _parse_linha(linhas[pid - 1]):
        raise ErroEdicao("Essa prova não existe mais. Recarregue a página.", 404)
    antiga = _parse_linha(linhas[pid - 1])
    del linhas[pid - 1]
    _gravar(cam, "\n".join(linhas))
    _apagar_logo_se_sem_uso(pasta, antiga["logo"], linhas)


# --------------------------------------------------------------------- perfil --
def ler_perfil(pasta):
    texto = _ler(os.path.join(pasta, "perfil.txt"))
    dados = {}
    for linha in _linhas(texto):
        s = linha.strip()
        if s and not s.startswith("#") and ":" in s:
            k, v = s.split(":", 1)
            dados[k.strip().lower()] = v.strip()
    return {"nome": dados.get("nome", ""), "frase": dados.get("frase", ""), "foto": dados.get("foto", ""),
            "strava": dados.get("strava", ""), "garmin": dados.get("garmin", "")}, versao(texto)


def salvar_perfil(pasta, d, v_arquivo=None):
    cam = os.path.join(pasta, "perfil.txt")
    texto = _ler(cam)
    if os.path.exists(cam):
        _checar_versao(texto, v_arquivo)
    texto = texto or corredor.MODELO_PERFIL
    atual, _ = ler_perfil(pasta)
    nome = " ".join(str(d.get("nome", atual["nome"]) or "").split())[:80]
    frase = " ".join(str(d.get("frase", atual["frase"]) or "").split())[:160]
    if not nome:
        raise ErroEdicao("Informe o seu nome.")
    links = {}
    for k, rot in (("strava", "Strava"), ("garmin", "Garmin Connect")):
        bruto = " ".join(str(d.get(k, atual[k]) or "").split())
        links[k] = corredor.link_valido(k, bruto) if bruto else ""
        if bruto and not links[k]:
            raise ErroEdicao(f"O link do {rot} precisa ser um endereço https do próprio {rot}.")
    foto = atual["foto"]
    if d.get("foto_b64"):
        novo = salvar_imagem(os.path.join(pasta, "imagens"), "foto", d.get("foto_ext"), d["foto_b64"])
        if re.fullmatch(r"foto-[0-9a-f]{6}\.(png|jpg|webp|gif|svg)", foto or ""):
            try:
                os.remove(os.path.join(pasta, "imagens", foto))
            except OSError:
                pass
        foto = novo
    novos = {"nome": nome, "frase": frase, "foto": foto, **links}
    linhas, vistos = [], set()
    for linha in _linhas(texto):
        s = linha.strip()
        if s and not s.startswith("#") and ":" in s:
            k = s.split(":", 1)[0].strip().lower()
            if k in novos:
                linhas.append(f"{k}: {novos[k]}")
                vistos.add(k)
                continue
        linhas.append(linha)
    while linhas and linhas[-1] == "":
        linhas.pop()
    for k, v in novos.items():
        if k not in vistos:
            linhas.append(f"{k}: {v}")
    _gravar(cam, "\n".join(linhas) + "\n")
    return novos

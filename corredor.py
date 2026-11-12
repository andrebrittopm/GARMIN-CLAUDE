"""Perfil do corredor e provas, lidos de arquivos de texto simples.

Tudo aqui é TEXTO e IMAGEM que você fornece (nome, frase, foto, logos, nome e data
das provas). Números de desempenho (tempo, pace, distância percorrida) vêm SEMPRE
da Garmin: a prova já corrida é ligada à atividade do mesmo dia.

Arquivos (na pasta dos dados):
  perfil.txt            nome:, frase:, foto:
  provas.txt            data; nome; distância em km; logo (opcional)
  imagens/foto.jpg      sua foto
  imagens/corridas/...  logos das provas
Linhas começadas com # são comentários.
"""
import base64
import datetime as dt
import os

from formatos import eh_corrida

TIPOS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml"}
LIMITE_BYTES = 2_500_000
TOLERANCIA_DIST = 0.20      # a atividade precisa ter distância até 20% do informado

MODELO_PERFIL = """# Seu perfil. Linhas com # são ignoradas. Edite no Bloco de Notas e salve.
nome: Seu Nome
frase: Corredor desde 2024
# nome do arquivo da sua foto, que deve estar dentro da pasta imagens
foto: foto.jpg
"""
MODELO_PROVAS = """# Uma prova por linha:  data; nome; distância em km; arquivo do logo (opcional)
# A data pode ser AAAA-MM-DD ou DD/MM/AAAA. O logo fica na pasta imagens/corridas.
# Provas já corridas ganham tempo e pace da Garmin (pela data); as futuras ganham contagem.
# Exemplos (apague e coloque as suas):
# 2026-10-18; 10K Noturna; 10; 10k-noturna.png
# 06/12/2026; Corrida de Fim de Ano; 10;
"""


def criar_modelos(pasta):
    """Cria perfil.txt, provas.txt e as pastas de imagens, sem sobrescrever nada."""
    feitos = []
    for nome, texto in (("perfil.txt", MODELO_PERFIL), ("provas.txt", MODELO_PROVAS)):
        p = os.path.join(pasta, nome)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(texto)
            feitos.append(nome)
    os.makedirs(os.path.join(pasta, "imagens", "corridas"), exist_ok=True)
    return feitos


def _linhas(caminho):
    try:
        with open(caminho, encoding="utf-8-sig") as f:
            return [(n, x.strip()) for n, x in enumerate(f, 1)
                    if x.strip() and not x.strip().startswith("#")]
    except OSError:
        return None


def _bytes_ok(ext, dados):
    if ext == ".png":
        return dados.startswith(b"\x89PNG")
    if ext in (".jpg", ".jpeg"):
        return dados.startswith(b"\xff\xd8")
    if ext == ".gif":
        return dados.startswith(b"GIF8")
    if ext == ".webp":
        return dados[:4] == b"RIFF" and dados[8:12] == b"WEBP"
    if ext == ".svg":
        return b"<svg" in dados[:2000].lower()
    return False


def imagem_uri(pasta_base, nome, avisos, rotulo):
    """Imagem como data URI, ou None (com aviso). Só aceita um NOME de arquivo
    dentro da pasta indicada: nada de caminhos, nada de sair da pasta."""
    nome = (nome or "").strip()
    if not nome:
        return None
    if any(c in nome for c in "/\\:") or nome.startswith("."):
        avisos.append(f"{rotulo}: use só o nome do arquivo (ex.: foto.jpg), sem pastas.")
        return None
    ext = os.path.splitext(nome)[1].lower()
    if ext not in TIPOS:
        avisos.append(f"{rotulo}: tipo de arquivo não aceito ({ext or 'sem extensão'}). "
                      "Use png, jpg, webp, gif ou svg.")
        return None
    base = os.path.realpath(pasta_base)
    alvo = os.path.realpath(os.path.join(base, nome))
    if os.path.dirname(alvo) != base:
        avisos.append(f"{rotulo}: arquivo fora da pasta de imagens.")
        return None
    if not os.path.isfile(alvo):
        avisos.append(f"{rotulo}: não achei '{nome}' em {os.path.basename(base)}.")
        return None
    if os.path.getsize(alvo) > LIMITE_BYTES:
        avisos.append(f"{rotulo}: '{nome}' tem mais de {LIMITE_BYTES // 1_000_000} MB; "
                      "reduza a imagem para o painel não ficar pesado.")
        return None
    with open(alvo, "rb") as f:
        dados = f.read()
    if not _bytes_ok(ext, dados):
        avisos.append(f"{rotulo}: '{nome}' não parece ser uma imagem {ext}.")
        return None
    return f"data:{TIPOS[ext]};base64," + base64.b64encode(dados).decode("ascii")


def carregar_perfil(pasta, avisos):
    """None se não há perfil.txt; senão dict(nome, frase, foto_uri)."""
    linhas = _linhas(os.path.join(pasta, "perfil.txt"))
    if linhas is None:
        return None
    dados = {}
    for n, x in linhas:
        if ":" not in x:
            avisos.append(f"perfil.txt linha {n} ignorada (use o formato nome: valor).")
            continue
        k, v = x.split(":", 1)
        dados[k.strip().lower()] = v.strip()
    return {"nome": dados.get("nome") or "Corredor",
            "frase": dados.get("frase") or "",
            "foto_uri": imagem_uri(os.path.join(pasta, "imagens"), dados.get("foto"),
                                   avisos, "Foto")}


def _data(txt):
    txt = txt.strip()
    if "/" in txt:
        return dt.datetime.strptime(txt, "%d/%m/%Y").date()
    return dt.date.fromisoformat(txt)


def carregar_provas(pasta, avisos):
    """Lista de dicts (data, nome, dist_km, logo_uri). Linhas ruins são puladas."""
    linhas = _linhas(os.path.join(pasta, "provas.txt"))
    out = []
    for n, x in linhas or []:
        partes = [p.strip() for p in x.split(";")]
        if len(partes) < 2 or not partes[1]:
            avisos.append(f"provas.txt linha {n} ignorada (use: data; nome; distância; logo).")
            continue
        try:
            data = _data(partes[0])
        except ValueError:
            avisos.append(f"provas.txt linha {n} ignorada: data inválida '{partes[0]}'.")
            continue
        dist = None
        if len(partes) > 2 and partes[2]:
            try:
                dist = float(partes[2].lower().replace("km", "").replace(",", ".").strip())
                if not 0 < dist < 1000:
                    raise ValueError
            except ValueError:
                avisos.append(f"provas.txt linha {n}: distância '{partes[2]}' ignorada.")
                dist = None
        logo = imagem_uri(os.path.join(pasta, "imagens", "corridas"),
                          partes[3] if len(partes) > 3 else "", avisos,
                          f"Logo de '{partes[1]}'")
        out.append({"data": data, "nome": partes[1], "dist_km": dist, "logo_uri": logo})
    return sorted(out, key=lambda p: p["data"])


def atividade_da_prova(prova, historico, usadas=()):
    """Corrida do mesmo dia mais parecida com a prova (números da Garmin)."""
    cs = [a for a in historico if a["data"] == prova["data"].isoformat()
          and eh_corrida(a) and a["dist_m"] and a.get("id") not in usadas]
    if not cs:
        return None
    if prova["dist_km"]:
        alvo = prova["dist_km"] * 1000
        a = min(cs, key=lambda x: abs(x["dist_m"] - alvo))
        return a if abs(a["dist_m"] - alvo) <= TOLERANCIA_DIST * alvo else None
    return max(cs, key=lambda x: x["dist_m"])


def montar(pasta, historico, hoje, cobertura_ini=None):
    """Tudo que o painel precisa para o visual de corredor, ou None se o usuário
    não criou perfil.txt nem provas.txt."""
    avisos = []
    perfil = carregar_perfil(pasta, avisos)
    provas = carregar_provas(pasta, avisos)
    if perfil is None and not provas:
        return None
    usadas, proximas, feitas = set(), [], []
    for p in provas:
        if p["data"] > hoje:
            proximas.append({**p, "dias": (p["data"] - hoje).days})
        else:
            a = atividade_da_prova(p, historico, usadas)
            if a:
                usadas.add(a.get("id"))
            feitas.append({**p, "atv": a, "origem": "lista"})
    # corridas marcadas como competição na Garmin e que não estão na sua lista
    for a in historico:
        if (a.get("evento") == "race" and eh_corrida(a) and a.get("id") not in usadas
                and a["data"] and a["data"] <= hoje.isoformat()):
            feitas.append({"data": dt.date.fromisoformat(a["data"]), "nome": a.get("nome") or "Competição",
                           "dist_km": None, "logo_uri": None, "atv": a, "origem": "garmin"})
    feitas.sort(key=lambda p: p["data"], reverse=True)
    # soma do ano: só é "do ano" se o histórico guardado começa antes de 1º de janeiro
    ini_ano = dt.date(hoje.year, 1, 1)
    cob = dt.date.fromisoformat(cobertura_ini) if cobertura_ini else None
    desde = ini_ano if (cob is None or cob <= ini_ano) else cob
    cs = [a for a in historico if eh_corrida(a) and a["data"] and a["data"] >= desde.isoformat()]
    return {
        "perfil": perfil, "proximas": proximas, "feitas": feitas, "avisos": avisos,
        "periodo": {"desde": desde, "do_ano": desde == ini_ano,
                    "dist_m": sum(a["dist_m"] for a in cs if a["dist_m"]), "n": len(cs)},
    }

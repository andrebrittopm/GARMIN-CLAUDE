#!/usr/bin/env python3
"""Instala a biblioteca OFICIAL da Garmin para arquivos FIT (garmin-fit-sdk) em <programa>/libs,
sem pip e sem mexer no sistema (só Python padrão).

Segurança: a versão e o hash (sha256) saem do requirements-fit.txt do próprio projeto; o arquivo
é baixado só de pypi.org / files.pythonhosted.org por HTTPS e só é usado se o hash bater. O zip
é extraído com validação de caminhos (nada fora da pasta de destino).
Uso:  python3 instalar_fit.py [PASTA_DO_PROGRAMA]
Licença da biblioteca: FIT Protocol License Agreement (uso pessoal; não redistribuir).
"""
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from urllib.parse import urlparse

HOSTS_OK = {"pypi.org", "files.pythonhosted.org"}
LIMITE = 20_000_000


def erro(msg):
    print(f"ERRO: {msg}", file=sys.stderr)
    sys.exit(1)


def baixar(url, limite=LIMITE):
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in HOSTS_OK:
        erro("endereço de download não permitido.")
    req = urllib.request.Request(url, headers={"User-Agent": "painel-pessoal/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dados = r.read(limite + 1)
    if len(dados) > limite:
        erro("arquivo maior que o permitido.")
    return dados


def requisitos(pasta):
    txt = open(os.path.join(pasta, "requirements-fit.txt"), encoding="utf-8").read()
    m = re.search(r"^garmin-fit-sdk==([0-9.]+)", txt, re.M)
    h = re.search(r"--hash=sha256:([0-9a-f]{64})", txt)
    if not (m and h):
        erro("não entendi o requirements-fit.txt.")
    return m.group(1), h.group(1)


def extrair(zip_bytes, destino):
    base = os.path.realpath(destino)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for i in z.infolist():
            alvo = os.path.realpath(os.path.join(destino, i.filename))
            if not (alvo == base or alvo.startswith(base + os.sep)):
                erro(f"caminho suspeito dentro do arquivo: {i.filename[:60]}")
        z.extractall(destino)


def principal(pasta):
    versao, hash_esperado = requisitos(pasta)
    destino = os.path.join(pasta, "libs")
    if os.path.isdir(os.path.join(destino, f"garmin_fit_sdk-{versao}.dist-info")):
        print(f"garmin-fit-sdk {versao} já está instalado em {destino}.")
        return 0
    meta = json.loads(baixar(f"https://pypi.org/pypi/garmin-fit-sdk/{versao}/json", 2_000_000))
    arquivos = [u for u in meta.get("urls", []) if (u.get("digests") or {}).get("sha256") == hash_esperado
                and u.get("filename", "").endswith(".whl")]
    if not arquivos:
        erro("o PyPI não tem um arquivo com o hash esperado; nada foi instalado.")
    dados = baixar(arquivos[0]["url"])
    if hashlib.sha256(dados).hexdigest() != hash_esperado:
        erro("o hash do arquivo baixado não confere; nada foi instalado.")
    os.makedirs(destino, exist_ok=True)
    extrair(dados, destino)
    print(f"OK: garmin-fit-sdk {versao} instalado em {destino} (hash conferido).")
    return 0


if __name__ == "__main__":
    sys.exit(principal(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1
                       else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

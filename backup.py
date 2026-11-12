"""Cópia de segurança dos seus ARQUIVOS PESSOAIS (um ZIP) e restauração.

Entra no ZIP: perfil.txt, provas.txt, plano.json, config_painel.json e a pasta imagens
(foto e logos). Com --com-dados entram também dados_brutos.json (saúde) e rotas.json
(localização): o ZIP fica sensível, guarde-o com cuidado.
Nunca entram: a chave da Garmin, a do intervals.icu, o token (ficam só no cofre do Windows)
nem o programa (esse se recupera pelo GitHub).

Restaurar: só devolve os nomes acima (qualquer outro nome do ZIP é ignorado), recusa
caminhos estranhos, limita tamanhos e guarda o que seria sobrescrito em backup_restauracao/.
"""
import datetime as dt
import os
import re
import shutil
import zipfile

PASTA_BACKUPS = "backups_pessoais"
FIXOS = ["perfil.txt", "provas.txt", "plano.json", "config_painel.json"]
DADOS = ["dados_brutos.json", "rotas.json"]
EXT_IMAGEM = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
LIMITE_IMAGEM = 5_000_000
LIMITE_FIXO = 5_000_000
LIMITE_DADOS = 200_000_000
LIMITE_TOTAL = 400_000_000
MANTER = 10
NOME_IMAGEM = re.compile(r"imagens/(corridas/)?[^/\\:*?\"<>|]{1,120}")


class ErroBackup(Exception):
    """Mensagem segura para mostrar ao usuário."""


def _imagens(pasta):
    base = os.path.join(pasta, "imagens")
    for raiz, _, nomes in os.walk(base):
        rel = os.path.relpath(raiz, base).replace("\\", "/")
        if rel not in (".", "corridas"):        # só as duas pastas que o painel usa
            continue
        for n in sorted(nomes):
            if os.path.splitext(n)[1].lower() in EXT_IMAGEM and os.path.getsize(os.path.join(raiz, n)) <= LIMITE_IMAGEM:
                yield "imagens/" + (n if rel == "." else f"corridas/{n}"), os.path.join(raiz, n)


def criar(pasta, com_dados=False, agora=None):
    """Cria o ZIP e devolve (caminho, lista de nomes incluídos)."""
    agora = agora or dt.datetime.now()
    itens = [(n, os.path.join(pasta, n)) for n in FIXOS + (DADOS if com_dados else [])
             if os.path.isfile(os.path.join(pasta, n))]
    itens += list(_imagens(pasta))
    if not itens:
        raise ErroBackup("Não achei nenhum arquivo pessoal para guardar (perfil.txt, provas.txt, plano.json, imagens...).")
    destino = os.path.join(pasta, PASTA_BACKUPS)
    os.makedirs(destino, exist_ok=True)
    nome = f"pessoal-{agora.strftime('%Y%m%d-%H%M%S')}{'-com-dados' if com_dados else ''}.zip"
    cam = os.path.join(destino, nome)
    tmp = cam + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, orig in itens:
            z.write(orig, arc)
        z.writestr("LEIA-ME.txt", "Cópia dos arquivos pessoais do Painel Garmin, feita em "
                   + agora.strftime("%d/%m/%Y %H:%M") + ".\nPara restaurar: py garmin_painel.py --restaurar-backup ARQUIVO.zip\n"
                   + ("ATENÇÃO: contém dados de saúde e de localização.\n" if com_dados else ""))
    os.replace(tmp, cam)
    antigos = sorted(f for f in os.listdir(destino) if f.startswith("pessoal-") and f.endswith(".zip"))
    for f in antigos[:-MANTER]:
        try:
            os.remove(os.path.join(destino, f))
        except OSError:
            pass
    return cam, [a for a, _ in itens]


def _permitido(nome, tamanho):
    """Tipo e limite de tamanho do arquivo do ZIP, ou None se não pode ser restaurado."""
    nome = nome.replace("\\", "/")
    if nome in FIXOS:
        return "fixo" if tamanho <= LIMITE_FIXO else None
    if nome in DADOS:
        return "dados" if tamanho <= LIMITE_DADOS else None
    if NOME_IMAGEM.fullmatch(nome) and ".." not in nome and os.path.splitext(nome)[1].lower() in EXT_IMAGEM:
        return "imagem" if tamanho <= LIMITE_IMAGEM else None
    return None


def conteudo(zip_caminho):
    """{nome: tamanho} do que pode ser restaurado, e a lista do que será ignorado."""
    try:
        z = zipfile.ZipFile(zip_caminho)
    except (zipfile.BadZipFile, OSError):
        raise ErroBackup("Esse arquivo não é um ZIP válido (ou não consegui abrir).") from None
    boas, ignoradas, total = {}, [], 0
    with z:
        for i in z.infolist():
            if i.is_dir():
                continue
            total += i.file_size
            if _permitido(i.filename, i.file_size):
                boas[i.filename.replace("\\", "/")] = i.file_size
            elif i.filename != "LEIA-ME.txt":
                ignoradas.append(i.filename)
    if total > LIMITE_TOTAL:
        raise ErroBackup("O ZIP é grande demais para restaurar.")
    return boas, ignoradas


def restaurar(pasta, zip_caminho, perguntar=True, entrada=input, log=print, agora=None):
    boas, ignoradas = conteudo(zip_caminho)
    if not boas:
        raise ErroBackup("Esse ZIP não tem nenhum arquivo pessoal do painel; nada foi alterado.")
    log("Vai restaurar:")
    for n in sorted(boas):
        existe = os.path.exists(os.path.join(pasta, n))
        log(f"  {'substitui' if existe else 'novo     '} {n}")
    for n in ignoradas:
        log(f"  ignorado (não é arquivo pessoal do painel): {n[:80]}")
    if perguntar and entrada("Restaurar? O que for substituído fica guardado em backup_restauracao. [S/n] ").strip().lower() in ("n", "nao", "não"):
        log("Cancelado. Nada foi alterado.")
        return 0
    agora = agora or dt.datetime.now()
    guarda = os.path.join(pasta, "backup_restauracao", agora.strftime("%Y%m%d-%H%M%S"))
    base = os.path.realpath(pasta)
    with zipfile.ZipFile(zip_caminho) as z:
        for n in sorted(boas):
            alvo = os.path.realpath(os.path.join(pasta, *n.split("/")))
            if not alvo.startswith(base + os.sep):
                raise ErroBackup("Caminho inválido dentro do ZIP; nada foi alterado.")
            dados = z.read(n)
            if len(dados) > boas[n] + 1:
                raise ErroBackup("O ZIP não bate com o que declara; nada foi alterado.")
            if os.path.exists(alvo):
                os.makedirs(os.path.dirname(os.path.join(guarda, *n.split("/"))), exist_ok=True)
                shutil.copy2(alvo, os.path.join(guarda, *n.split("/")))
            os.makedirs(os.path.dirname(alvo), exist_ok=True)
            tmp = alvo + ".novo"
            with open(tmp, "wb") as f:
                f.write(dados)
            os.replace(tmp, alvo)
    log(f"Pronto! {len(boas)} arquivo(s) restaurado(s). Rode redesenhar.bat para ver o painel.")
    return 0

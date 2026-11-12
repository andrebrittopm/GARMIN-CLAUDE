"""Rotas (trilhas de GPS) a partir do arquivo FIT oficial de cada atividade.

- O arquivo vem do endpoint oficial de download (só leitura) como um ZIP.
- Quem lê o FIT é a biblioteca OFICIAL da Garmin (garmin-fit-sdk), instalada em ./libs
  com versão e hash fixos (requirements-fit.txt). Ela NÃO é copiada para o GitHub.
- Aqui só ficam pontos simplificados (até 300 por rota), num arquivo local.
- Nada é enviado a lugar nenhum: as rotas são desenhadas sozinhas, sem mapa de fundo.
"""
import io
import math
import os
import sys
import zipfile

PASTA_PROGRAMA = os.path.dirname(os.path.abspath(__file__))
SEMICIRCULOS = 180.0 / 2 ** 31          # semicírculos -> graus
MAX_PONTOS = 300
LIMITE_ZIP = 40_000_000                 # bytes aceitos na resposta
LIMITE_FIT = 60_000_000                 # bytes aceitos depois de abrir o ZIP
INSTALAR = ("py -m pip install --require-hashes --target libs -r requirements-fit.txt "
            "(dentro da pasta do painel)")


class ErroRota(Exception):
    """Mensagem segura (sem chave, token nem coordenadas)."""


def carregar_sdk():
    """Módulo garmin_fit_sdk, ou None se ainda não foi instalado em ./libs."""
    libs = os.path.join(PASTA_PROGRAMA, "libs")
    if os.path.isdir(libs) and libs not in sys.path:
        sys.path.append(libs)          # no fim: nunca sobrepõe nossos módulos
    try:
        import garmin_fit_sdk
        return garmin_fit_sdk
    except ImportError:
        return None


def versao_sdk():
    try:
        from importlib.metadata import version
        return version("garmin-fit-sdk")
    except Exception:
        return "?"


def extrair_fit(zip_bytes):
    """Primeiro arquivo .fit dentro do ZIP (com limite de tamanho)."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            fits = [i for i in z.infolist() if i.filename.lower().endswith(".fit")]
            if not fits:
                raise ErroRota("O ZIP da Garmin não contém um arquivo .fit.")
            info = fits[0]
            if info.file_size > LIMITE_FIT:
                raise ErroRota("O arquivo FIT é grande demais para ser lido.")
            return z.read(info)
    except zipfile.BadZipFile:
        # algumas respostas já vêm como FIT direto
        if zip_bytes[8:12] == b".FIT":
            return zip_bytes
        raise ErroRota("A resposta da Garmin não é um ZIP nem um arquivo FIT.") from None


def decodificar(fit_bytes):
    """Mensagens do FIT (dict nome -> lista). Levanta ErroRota se não for válido."""
    sdk = carregar_sdk()
    if sdk is None:
        raise ErroRota("A biblioteca oficial da Garmin (garmin-fit-sdk) não está instalada. "
                       "Instale com: " + INSTALAR)
    stream = sdk.Stream.from_bytes_io(io.BytesIO(fit_bytes))
    dec = sdk.Decoder(stream)
    if not dec.is_fit():
        raise ErroRota("O arquivo não é um FIT válido.")
    mesgs, erros = dec.read(apply_scale_and_offset=True, convert_datetimes_to_dates=False,
                            convert_types_to_strings=True, enable_crc_check=True,
                            merge_heart_rates=False)
    if erros and not mesgs.get("record_mesgs"):
        raise ErroRota(f"Falha ao ler o FIT ({len(erros)} erro(s)).")
    return mesgs


def pontos_gps(mesgs):
    """Lista de (lat, lon) em graus, só dos registros que têm GPS válido."""
    out = []
    for r in mesgs.get("record_mesgs", []):
        la, lo = r.get("position_lat"), r.get("position_long")
        if isinstance(la, (int, float)) and isinstance(lo, (int, float)):
            lat, lon = la * SEMICIRCULOS, lo * SEMICIRCULOS
            if -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0):
                out.append((lat, lon))
    return out


def distancia_m(a, b):
    """Distância aproximada entre dois pontos (m), boa para trechos curtos."""
    kx = 111_320 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((b[1] - a[1]) * kx, (b[0] - a[0]) * 110_540)


def comprimento_m(pts):
    return sum(distancia_m(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def simplificar(pts, maximo=MAX_PONTOS):
    """Reduz a trilha a, no máximo, `maximo` pontos, mantendo a forma (primeiro,
    último e os pontos mais espaçados no percurso)."""
    if len(pts) <= maximo:
        return list(pts)
    acum, total = [0.0], 0.0
    for i in range(len(pts) - 1):
        total += distancia_m(pts[i], pts[i + 1])
        acum.append(total)
    if total == 0:
        return [pts[0], pts[-1]]
    saida, j = [pts[0]], 1
    for k in range(1, maximo - 1):
        alvo = total * k / (maximo - 1)
        while j < len(pts) - 1 and acum[j] < alvo:
            j += 1
        if pts[j] != saida[-1]:
            saida.append(pts[j])
    saida.append(pts[-1])
    return saida


def cortar_pontas(pts, metros):
    """Remove os primeiros e os últimos `metros` da trilha (privacidade)."""
    if metros <= 0 or len(pts) < 3:
        return list(pts)
    n = len(pts)
    i = 0
    acc = 0.0
    while i < n - 1 and acc < metros:
        acc += distancia_m(pts[i], pts[i + 1])
        i += 1
    j, acc = n - 1, 0.0
    while j > i and acc < metros:
        acc += distancia_m(pts[j], pts[j - 1])
        j -= 1
    return pts[i:j + 1] if j - i >= 2 else []


def resumo(mesgs, pts):
    """Fatos sobre o arquivo, SEM coordenadas (para o teste e o diagnóstico)."""
    contagem = {k: len(v) for k, v in mesgs.items() if isinstance(v, list)}
    regs = mesgs.get("record_mesgs", [])
    campos = {}
    for nome, chaves in (("altitude", ("enhanced_altitude", "altitude")),
                         ("frequência cardíaca", ("heart_rate",)),
                         ("velocidade", ("enhanced_speed", "speed")),
                         ("cadência", ("cadence",)),
                         ("distância acumulada", ("distance",))):
        campos[nome] = any(isinstance(r.get(c), (int, float)) for r in regs for c in chaves)
    ext = None
    if pts:
        lats, lons = [p[0] for p in pts], [p[1] for p in pts]
        centro = (sum(lats) / len(lats), sum(lons) / len(lons))
        ext = (distancia_m((centro[0], min(lons)), (centro[0], max(lons))),
               distancia_m((min(lats), centro[1]), (max(lats), centro[1])))
    return {"mensagens": contagem, "registros": len(regs), "com_gps": len(pts),
            "campos": campos, "extensao_m": ext,
            "comprimento_m": comprimento_m(pts) if pts else 0.0,
            "esporte": [s.get("sport") for s in mesgs.get("session_mesgs", [])][:1]}

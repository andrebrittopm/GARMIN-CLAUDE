"""Rotas (trilhas de GPS) a partir do arquivo FIT oficial de cada atividade.

- O arquivo vem do endpoint oficial de download (só leitura) como um ZIP.
- Quem lê o FIT é a biblioteca OFICIAL da Garmin (garmin-fit-sdk), instalada em ./libs
  com versão e hash fixos (requirements-fit.txt). Ela NÃO é copiada para o GitHub.
- Aqui só ficam pontos simplificados (até 300 por rota), num arquivo local.
- Nada é enviado a lugar nenhum: as rotas são desenhadas sozinhas, sem mapa de fundo.
"""
import io
import json
import math
import os
import sys
import time
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


def perfil_altitude(mesgs, maximo=150):
    """[[distância_m, altitude_m], ...] dos registros que têm os dois valores (números
    do próprio FIT, sem estimativas), reduzido a no máximo `maximo` pontos."""
    pts = []
    for r in mesgs.get("record_mesgs", []):
        d = r.get("distance")
        a = r.get("enhanced_altitude") if isinstance(r.get("enhanced_altitude"), (int, float)) else r.get("altitude")
        if isinstance(d, (int, float)) and isinstance(a, (int, float)) and -500 < a < 9000 and d >= 0:
            pts.append((float(d), float(a)))
    if len(pts) < 2:
        return []
    if len(pts) > maximo:
        passo = (len(pts) - 1) / (maximo - 1)
        pts = [pts[round(i * passo)] for i in range(maximo)]
    return [[round(d), round(a, 1)] for d, a in pts]


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


# ------------------------------------------------------------------ guarda ---
ARQUIVO = "rotas.json"
PRIVACIDADE_PADRAO_M = 300
POR_EXECUCAO = 8          # trilhas baixadas por atualização normal (o resto, aos poucos)
MAX_TENTATIVAS = 3


def caminho_rotas(pasta):
    return os.path.join(pasta, ARQUIVO)


def carregar_rotas(pasta):
    """{id_da_atividade(str): {pts, ...} | {sem_gps: true} | {falhou: n}}"""
    try:
        with open(caminho_rotas(pasta), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def salvar_rotas(pasta, dados):
    cam = caminho_rotas(pasta)
    tmp = cam + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, separators=(",", ":"))
    for n in range(4):
        try:
            os.replace(tmp, cam)
            return
        except OSError:
            if n == 3:
                raise
            time.sleep(0.5 * (n + 1))


def arredondar(pts):
    """~1 m de precisão: suficiente para desenhar e menor para guardar."""
    return [[round(la, 5), round(lo, 5)] for la, lo in pts]


def e_corrida(a):
    return "running" in ((a.get("activityType") or {}).get("typeKey") or "")


def _completa(v):
    """Entrada de rotas.json que não precisa mais ser baixada."""
    if v.get("sem_gps"):
        return True
    if v.get("falhou", 0) >= MAX_TENTATIVAS:
        return True
    return "pts" in v and "alt" in v


def pendentes(atividades_brutas, guardadas):
    """Corridas (mais recentes primeiro) cuja trilha ou altitude ainda não foi guardada."""
    out = [a for a in atividades_brutas
           if e_corrida(a) and not _completa(guardadas.get(str(a.get("activityId")), {}))]
    return sorted(out, key=lambda a: a.get("startTimeLocal") or "", reverse=True)


def buscar_trilhas(cli, atividades_brutas, guardadas, limite=POR_EXECUCAO, progresso=None):
    """Baixa o FIT das corridas pendentes (só leitura) e guarda a trilha simplificada.
    Devolve (quantas_novas, avisos). Uma falha não derruba as outras."""
    if carregar_sdk() is None:
        return 0, ["Rotas desativadas: a biblioteca oficial (garmin-fit-sdk) não está instalada. "
                   "Instale com: " + INSTALAR]
    novas, avisos = 0, []
    for a in pendentes(atividades_brutas, guardadas)[:limite]:
        k = str(a.get("activityId"))
        # esteira/GPS desligado: a Garmin informa a latitude de partida como vazia.
        # Se o campo nem existe na resposta, não dá para saber: tenta baixar.
        if "startLatitude" in a and a["startLatitude"] is None:
            guardadas[k] = {"sem_gps": True}
            continue
        try:
            fit = extrair_fit(cli.get_bytes(f"/download-service/files/activity/{k}", LIMITE_ZIP))
            mesgs = decodificar(fit)
            pts = pontos_gps(mesgs)
            if len(pts) < 10:
                guardadas[k] = {"sem_gps": True}
            else:
                guardadas[k] = {"pts": arredondar(simplificar(pts)),
                                "gps_m": round(comprimento_m(pts)),
                                "alt": perfil_altitude(mesgs)}
                novas += 1
        except Exception as e:                             # nunca mostra detalhes
            msg = str(e)
            atual = guardadas.get(k, {})
            guardadas[k] = {**atual, "falhou": atual.get("falhou", 0) + 1}   # mantém a trilha que já existe
            if "429" in msg:
                avisos.append("A Garmin pediu para esperar (muitos pedidos); as trilhas "
                              "que faltam serão baixadas na próxima atualização.")
                break
        if progresso:
            progresso()
        time.sleep(0.4)
    return novas, avisos


# --------------------------------------------------------- desenho e agrupar -
def projetar(pts, lat0=None):
    """(lat, lon) -> (x, y) em km, com y para baixo (como no desenho)."""
    if not pts:
        return []
    lat0 = sum(p[0] for p in pts) / len(pts) if lat0 is None else lat0
    kx = 111.32 * math.cos(math.radians(lat0))
    return [(p[1] * kx, -p[0] * 110.54) for p in pts]


def centro(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def area_principal(rotas, raio_km=25.0):
    """Entre várias rotas (cada uma: lista de [lat, lon]), as que ficam na região
    com mais corridas. Devolve (indices_da_regiao, quantas_ficaram_de_fora)."""
    if not rotas:
        return [], 0
    cs = [centro(r) for r in rotas]
    melhor = []
    for c in cs:
        perto = [i for i, d in enumerate(cs) if distancia_m(c, d) <= raio_km * 1000]
        if len(perto) > len(melhor):
            melhor = perto
    return melhor, len(rotas) - len(melhor)

"""Armazém local dos dados brutos da Garmin (sem chave e sem token).

Guarda a resposta da Garmin como veio, por data, para:
- só buscar o que é novo nas próximas execuções (atualização rápida);
- redesenhar o painel sem chamar a Garmin (`--so-visual`);
- manter histórico além da janela do painel.
O arquivo tem dados de saúde: fica só no seu computador (fora do GitHub).
"""
import datetime as dt
import glob
import json
import os
import shutil
import time

VERSAO = 1
RECENTE_DIAS = 10     # sempre refaz os últimos dias (sono e VFC chegam depois)
SOBREPOSICAO = 3      # e volta 3 dias a partir da última busca


def vazio():
    return {"versao": VERSAO, "cobertura_ini": None, "ultima_busca": None,
            "resumos": {}, "sonos": {}, "vfc": {}, "peso": {}, "atividades": {}}


def _valido(d):
    return (isinstance(d, dict) and d.get("versao") == VERSAO
            and isinstance(d.get("resumos"), dict)
            and isinstance(d.get("sonos"), dict)
            and isinstance(d.get("vfc"), dict)
            and isinstance(d.get("atividades"), dict))


def carregar(caminho):
    """Lê o armazém. Arquivo ausente = vazio. Arquivo ilegível NÃO é apagado:
    é renomeado para dados_brutos.corrompido-<data>.json, para não perder
    histórico por engano, e o programa recomeça com um armazém novo."""
    try:
        with open(caminho, encoding="utf-8") as f:
            d = json.load(f)
        if _valido(d):
            return d
        motivo = "formato desconhecido"
    except FileNotFoundError:
        return vazio()
    except (OSError, ValueError):
        motivo = "arquivo ilegível"
    destino = f"{caminho[:-5] if caminho.endswith('.json') else caminho}" \
              f".corrompido-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    try:
        os.replace(caminho, destino)
        print(f"AVISO: o arquivo de dados guardados estava com problema ({motivo}); "
              f"foi separado em {os.path.basename(destino)} e a busca recomeça do zero.")
    except OSError:
        print(f"AVISO: o arquivo de dados guardados está com problema ({motivo}).")
    return vazio()


def backup_diario(caminho, manter=5, hoje=None):
    """Uma cópia por dia em backups/, guardando só as últimas `manter`.
    Só copia se o arquivo atual está íntegro. Devolve o caminho criado ou None."""
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as f:
            if not _valido(json.load(f)):
                return None
    except (OSError, ValueError):
        return None
    pasta = os.path.join(os.path.dirname(os.path.abspath(caminho)), "backups")
    os.makedirs(pasta, exist_ok=True)
    nome = f"dados_brutos-{(hoje or dt.date.today()).isoformat()}.json"
    destino, criado = os.path.join(pasta, nome), None
    if not os.path.exists(destino):
        shutil.copy2(caminho, destino)
        criado = destino
    antigos = sorted(glob.glob(os.path.join(pasta, "dados_brutos-*.json")))
    for velho in antigos[:-manter] if manter > 0 else antigos:
        try:
            os.remove(velho)
        except OSError:
            pass
    return criado


def listar_backups(caminho):
    pasta = os.path.join(os.path.dirname(os.path.abspath(caminho)), "backups")
    return sorted(glob.glob(os.path.join(pasta, "dados_brutos-*.json")))


def salvar(caminho, dados, tentativas=4):
    """Grava com segurança. Pastas sincronizadas (OneDrive) podem bloquear o
    arquivo por instantes, então tenta de novo antes de desistir (OSError)."""
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)
    for n in range(tentativas):
        try:
            os.replace(tmp, caminho)
            return
        except OSError:
            if n == tentativas - 1:
                raise
            time.sleep(0.5 * (n + 1))


def planejar(dados, hoje, ini_painel):
    """Lista de janelas (inicio, fim) a buscar na Garmin."""
    cob, ult = dados.get("cobertura_ini"), dados.get("ultima_busca")
    if not cob or not ult:
        return [(ini_painel, hoje)]
    cob, ult = dt.date.fromisoformat(cob), dt.date.fromisoformat(ult)
    ini_recente = max(cob, min(hoje - dt.timedelta(days=RECENTE_DIAS - 1),
                               ult - dt.timedelta(days=SOBREPOSICAO)))
    for chave in ("vfc_pendente_ini", "peso_pendente_ini"):   # buscas que falharam antes
        pend = dados.get(chave)
        if pend:
            ini_recente = min(ini_recente, max(cob, dt.date.fromisoformat(pend)))
    jan = [(ini_recente, hoje)]
    if ini_painel < cob:
        jan.insert(0, (ini_painel, cob - dt.timedelta(days=1)))
    return jan


def _data_ativ(a):
    return (a.get("startTimeLocal") or "")[:10]


def mesclar(dados, janela, resumos, sonos, vfc, atividades, peso=None):
    """Aplica o resultado de UMA janela (a, b) ao armazém."""
    a, b = janela[0].isoformat(), janela[1].isoformat()
    for r in resumos:
        if isinstance(r, dict) and r.get("calendarDate"):
            dados["resumos"][r["calendarDate"]] = r
    for s in sonos:
        if isinstance(s, dict) and isinstance(s.get("dailySleepDTO"), dict):
            s = s["dailySleepDTO"]
        if isinstance(s, dict) and s.get("calendarDate"):
            dados["sonos"][s["calendarDate"]] = s
    dados["vfc"].update(vfc)
    dados.setdefault("peso", {}).update(peso or {})
    # atividades: o que a Garmin devolveu para a janela substitui o guardado.
    # Lista vazia não apaga nada: pode ser falha passageira, e é mais seguro
    # manter o que já estava guardado.
    if atividades:
        for k in [k for k, v in dados["atividades"].items() if a <= _data_ativ(v) <= b]:
            del dados["atividades"][k]
    for x in atividades:
        if isinstance(x, dict) and x.get("activityId") is not None:
            dados["atividades"][str(x["activityId"])] = x


def marcar_pendente(dados, nome, janela, ok):
    """Lembra de refazer uma busca que falhou (nome: 'vfc' ou 'peso'); limpa
    quando a janela refeita deu certo e chegou até hoje."""
    chave = f"{nome}_pendente_ini"
    pend = dados.get(chave)
    if not ok:
        ini = janela[0].isoformat()
        dados[chave] = min(pend, ini) if pend else ini
    elif pend and janela[0].isoformat() <= pend and janela[1] >= dt.date.today():
        dados.pop(chave, None)


def marcar_vfc(dados, janela, ok):
    marcar_pendente(dados, "vfc", janela, ok)


def fechar(dados, hoje, ini_painel):
    cob = dados.get("cobertura_ini")
    novo = ini_painel.isoformat() if not cob else min(cob, ini_painel.isoformat())
    dados["cobertura_ini"] = novo
    dados["ultima_busca"] = hoje.isoformat()
    dados["atualizado_em"] = dt.datetime.now().isoformat(timespec="seconds")


def recorte(dados, ini, fim):
    """Dados do armazém dentro de [ini, fim], como a Garmin enviou:
    (resumos, sonos, vfc, atividades, peso)."""
    a, b = ini.isoformat(), fim.isoformat()
    dentro = lambda d: a <= (d or "") <= b  # noqa: E731
    return ([v for k, v in sorted(dados["resumos"].items()) if dentro(k)],
            [v for k, v in sorted(dados["sonos"].items()) if dentro(k)],
            {k: v for k, v in dados["vfc"].items() if dentro(k)},
            [v for v in dados["atividades"].values() if dentro(_data_ativ(v))],
            {k: v for k, v in dados.get("peso", {}).items() if dentro(k)})


def todas_atividades(dados):
    """Todas as atividades guardadas (histórico completo), como a Garmin enviou."""
    return list(dados["atividades"].values())

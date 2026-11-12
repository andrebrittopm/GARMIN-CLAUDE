"""Armazém local dos dados brutos da Garmin (sem chave e sem token).

Guarda a resposta da Garmin como veio, por data, para:
- só buscar o que é novo nas próximas execuções (atualização rápida);
- redesenhar o painel sem chamar a Garmin (`--so-visual`);
- manter histórico além da janela do painel.
O arquivo tem dados de saúde: fica só no seu computador (fora do GitHub).
"""
import datetime as dt
import json
import os
import time

VERSAO = 1
RECENTE_DIAS = 10     # sempre refaz os últimos dias (sono e VFC chegam depois)
SOBREPOSICAO = 3      # e volta 3 dias a partir da última busca


def vazio():
    return {"versao": VERSAO, "cobertura_ini": None, "ultima_busca": None,
            "resumos": {}, "sonos": {}, "vfc": {}, "atividades": {}}


def carregar(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("versao") == VERSAO and isinstance(d.get("resumos"), dict):
            return d
    except (OSError, ValueError):
        pass
    return vazio()


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
    pend = dados.get("vfc_pendente_ini")      # VFC que falhou numa execução anterior
    if pend:
        ini_recente = min(ini_recente, max(cob, dt.date.fromisoformat(pend)))
    jan = [(ini_recente, hoje)]
    if ini_painel < cob:
        jan.insert(0, (ini_painel, cob - dt.timedelta(days=1)))
    return jan


def _data_ativ(a):
    return (a.get("startTimeLocal") or "")[:10]


def mesclar(dados, janela, resumos, sonos, vfc, atividades):
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
    # atividades: o que a Garmin devolveu para a janela substitui o guardado.
    # Lista vazia não apaga nada: pode ser falha passageira, e é mais seguro
    # manter o que já estava guardado.
    if atividades:
        for k in [k for k, v in dados["atividades"].items() if a <= _data_ativ(v) <= b]:
            del dados["atividades"][k]
    for x in atividades:
        if isinstance(x, dict) and x.get("activityId") is not None:
            dados["atividades"][str(x["activityId"])] = x


def marcar_vfc(dados, janela, ok):
    """Lembra de refazer a VFC se ela falhou; limpa quando a janela refeita deu certo."""
    pend = dados.get("vfc_pendente_ini")
    if not ok:
        ini = janela[0].isoformat()
        dados["vfc_pendente_ini"] = min(pend, ini) if pend else ini
    elif pend and janela[0].isoformat() <= pend and janela[1] >= dt.date.today():
        dados.pop("vfc_pendente_ini", None)


def fechar(dados, hoje, ini_painel):
    cob = dados.get("cobertura_ini")
    novo = ini_painel.isoformat() if not cob else min(cob, ini_painel.isoformat())
    dados["cobertura_ini"] = novo
    dados["ultima_busca"] = hoje.isoformat()
    dados["atualizado_em"] = dt.datetime.now().isoformat(timespec="seconds")


def recorte(dados, ini, fim):
    """Dados do armazém dentro de [ini, fim] (listas, como a Garmin enviou)."""
    a, b = ini.isoformat(), fim.isoformat()
    dentro = lambda d: a <= (d or "") <= b  # noqa: E731
    return ([v for k, v in sorted(dados["resumos"].items()) if dentro(k)],
            [v for k, v in sorted(dados["sonos"].items()) if dentro(k)],
            {k: v for k, v in dados["vfc"].items() if dentro(k)},
            [v for v in dados["atividades"].values() if dentro(_data_ativ(v))])

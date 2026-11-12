"""Configurações simples do painel (sem segredos), em config_painel.json.

Hoje guarda só a data em que a chave da Garmin vence, para o painel avisar
antes de ela parar de funcionar. A data aparece no site do Garmin Connect, em
https://connect.garmin.com/app/settings/personalApiToken
"""
import datetime as dt
import json
import os

ARQUIVO = "config_painel.json"
AVISAR_DIAS = 14


def _caminho(pasta):
    return os.path.join(pasta, ARQUIVO)


def carregar(pasta):
    try:
        with open(_caminho(pasta), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def salvar(pasta, dados):
    with open(_caminho(pasta), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


def definir_vencimento(pasta, texto):
    """Aceita AAAA-MM-DD ou DD/MM/AAAA. Levanta ValueError se for inválida."""
    texto = texto.strip()
    try:
        data = (dt.datetime.strptime(texto, "%d/%m/%Y").date() if "/" in texto
                else dt.date.fromisoformat(texto))
    except ValueError:
        raise ValueError("Data inválida. Use AAAA-MM-DD (ex.: 2027-02-09) "
                         "ou DD/MM/AAAA.") from None
    d = carregar(pasta)
    d["chave_vence"] = data.isoformat()
    salvar(pasta, d)
    return data


def vencimento(pasta, hoje=None):
    """(data, dias_restantes) ou None se o usuário ainda não informou."""
    try:
        data = dt.date.fromisoformat(carregar(pasta).get("chave_vence") or "")
    except ValueError:
        return None
    return data, (data - (hoje or dt.date.today())).days


def alerta(pasta, hoje=None):
    """Texto de alerta se a chave vence em até AVISAR_DIAS dias (ou já venceu)."""
    v = vencimento(pasta, hoje)
    if not v:
        return None
    data, dias = v
    br = data.strftime("%d/%m/%Y")
    if dias < 0:
        return (f"A chave da Garmin venceu em {br}. Crie outra no Garmin Connect "
                "e guarde-a de novo no cofre; sem isso o painel não atualiza.")
    if dias <= AVISAR_DIAS:
        quando = "hoje" if dias == 0 else ("amanhã" if dias == 1 else f"em {dias} dias")
        return (f"A chave da Garmin vence {quando} ({br}). Crie outra no Garmin "
                "Connect antes disso e guarde-a de novo no cofre.")
    return None


def privacidade_m(pasta):
    """Metros cortados do começo e do fim de cada rota desenhada (padrão 300)."""
    v = carregar(pasta).get("privacidade_m")
    return int(v) if isinstance(v, (int, float)) and 0 <= v <= 2000 else 300


def definir_privacidade(pasta, metros):
    if not 0 <= metros <= 2000:
        raise ValueError("Use um valor entre 0 e 2000 metros.")
    d = carregar(pasta)
    d["privacidade_m"] = int(metros)
    salvar(pasta, d)
    return int(metros)


def remover_vencimento(pasta):
    d = carregar(pasta)
    d.pop("chave_vence", None)
    salvar(pasta, d)

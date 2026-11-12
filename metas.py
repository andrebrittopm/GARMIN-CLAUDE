"""Metas definidas pelo USUÁRIO (ex.: 50 km por mês) e o progresso delas.

A meta é sua; o número realizado vem da Garmin (soma das corridas). O painel só
mostra o progresso, sem dizer o que fazer. Guardadas em config_painel.json.
"""
import datetime as dt

import configuracao
from formatos import eh_corrida, num, segunda

# nome na linha de comando -> (rótulo, unidade, período)
METAS = {
    "km-semana": ("Distância na semana", "km", "semana"),
    "corridas-semana": ("Corridas na semana", "corridas", "semana"),
    "km-mes": ("Distância no mês", "km", "mês"),
    "horas-mes": ("Tempo correndo no mês", "h", "mês"),
}
MAXIMO = 100000


def definir(pasta, texto):
    """`nome=valor`. Levanta ValueError se o nome ou o valor forem inválidos."""
    if "=" not in texto:
        raise ValueError("Use o formato nome=valor, por exemplo: km-mes=50")
    nome, valor = (x.strip().lower() for x in texto.split("=", 1))
    if nome not in METAS:
        raise ValueError("Meta desconhecida. Opções: " + ", ".join(METAS))
    try:
        v = float(valor.replace(",", "."))
    except ValueError:
        raise ValueError(f"'{valor}' não é um número.") from None
    if not 0 < v <= MAXIMO:
        raise ValueError(f"O valor deve ser maior que 0 e até {MAXIMO}.")
    d = configuracao.carregar(pasta)
    d.setdefault("metas", {})[nome] = v
    configuracao.salvar(pasta, d)
    return nome, v


def remover(pasta, nome):
    nome = nome.strip().lower()
    d = configuracao.carregar(pasta)
    if nome not in d.get("metas", {}):
        raise ValueError("Essa meta não está definida.")
    del d["metas"][nome]
    configuracao.salvar(pasta, d)


def listar(pasta):
    m = configuracao.carregar(pasta).get("metas") or {}
    return {k: v for k, v in m.items() if k in METAS and isinstance(v, (int, float)) and v > 0}


def _janela(periodo, hoje):
    if periodo == "semana":
        ini = segunda(hoje)
        return ini, ini + dt.timedelta(days=6)
    ini = hoje.replace(day=1)
    prox = (ini + dt.timedelta(days=32)).replace(day=1)
    return ini, prox - dt.timedelta(days=1)


def progresso(pasta, atividades, hoje):
    """Lista de dicts (rotulo, atual, meta, unidade, pct, texto, periodo_txt)."""
    out = []
    for nome, meta in listar(pasta).items():
        rotulo, unidade, periodo = METAS[nome]
        ini, fim = _janela(periodo, hoje)
        cs = [a for a in atividades if eh_corrida(a) and a["data"]
              and ini.isoformat() <= a["data"] <= fim.isoformat()]
        if nome.startswith("km"):
            atual = sum(a["dist_m"] for a in cs if a["dist_m"] is not None) / 1000
        elif nome.startswith("horas"):
            atual = sum(a["dur_s"] for a in cs if a["dur_s"] is not None) / 3600
        else:
            atual = float(len(cs))
        casas = 0 if unidade == "corridas" else 1
        out.append({
            "nome": nome, "rotulo": rotulo, "atual": atual, "meta": meta,
            "pct": round(atual / meta * 100),
            "texto": f"{num(atual, casas)} de {num(meta, 0 if float(meta).is_integer() else casas)} {unidade}",
            "periodo": f"{ini.day:02d}/{ini.month:02d} a {fim.day:02d}/{fim.month:02d}",
        })
    return out


def salvar_todas(pasta, valores):
    """valores: {nome: número | None | ''}. Vazio/None remove a meta. Valida tudo antes de gravar."""
    novos = {}
    for nome, v in (valores or {}).items():
        if nome not in METAS:
            raise ValueError("Meta desconhecida: " + str(nome)[:30])
        if v in (None, ""):
            continue
        try:
            x = float(str(v).replace(",", "."))
        except ValueError:
            raise ValueError(f"'{v}' não é um número ({METAS[nome][0]}).") from None
        if not 0 < x <= MAXIMO:
            raise ValueError(f"{METAS[nome][0]}: use um valor maior que 0 e até {MAXIMO}.")
        novos[nome] = x
    d = configuracao.carregar(pasta)
    d["metas"] = novos
    configuracao.salvar(pasta, d)
    return novos

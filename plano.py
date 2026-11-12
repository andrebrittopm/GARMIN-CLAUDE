"""Plano de treino e meta de prova (opcional), lido de plano.json.

O que é SEU (a meta, as datas dos ciclos e dos testes, o perfil de altitude da prova)
vem do arquivo plano.json, que você mantém no outro projeto ou à mão. Todo número de
desempenho (distância, tempo, ritmo) vem SEMPRE da Garmin. O que é cálculo é dito:

- Equivalente em 10 km: fórmula de Riegel, tempo x (10 / distância) ** 1,06. Só para
  corridas de 5 km ou mais.
- Previsão para outra distância: a mesma fórmula, a partir do melhor equivalente.
- Plano de prova: divide o tempo escolhido em ritmo uniforme; só quando o plano traz o
  perfil de altitude da prova (10 km), ajusta pelo relevo (custo de correr em subida e
  descida de Minetti, 2002).
Sem plano.json, nada disso aparece e o resto do painel não muda.

Formato (exemplo em GUIA.md):
  {"inicio": "2026-10-08",
   "prova": {"nome": "...", "data": "2027-07-04", "dist_km": 10, "meta_min": 41.5,
             "altitude_km": [636, 648, ... 11 valores, de 0 a 10 km]},
   "marcos": [{"data": "2026-12-08", "marco": "Teste ciclo 8", "meta_min": 45.75}],
   "ciclos": [{"ciclo": 1, "inicio": "2026-10-08", "fim": "2026-10-15", "fase": "Base",
               "teste": null}],
   "selos": {"longao_km": [10, 12, 14], "equiv_10k_min": [45, 44, 43, 42, 41.5],
             "ritmo_s": [270, 249], "ciclo_km": [30, 40, 50]}}
"""
import datetime as dt
import json
import os

from formatos import SEM_DADO, eh_corrida, hms, num, pace

ARQUIVO = "plano.json"
EXPOENTE = 1.06                 # Riegel
MIN_EQUIV_M = 5000              # só corridas de 5 km ou mais geram equivalente
DISTANCIAS_PLANO = (5, 7, 10, 21, 42)
DIST_EXATA = {21: 21.0975, 42: 42.195}
JANELA_EQUIV_DIAS = 60          # "equivalente de hoje" = melhor dos últimos 60 dias
LIMITE_BYTES = 300_000
RESTO_DESCIDA = 0.6             # na descida o custo cai só 60% do que a conta diria


# ----------------------------------------------------------- leitura -------
def _data(t):
    try:
        return dt.date.fromisoformat(str(t))
    except ValueError:
        return None


def _num(v, lo, hi):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and lo < v <= hi else None


def carregar(pasta):
    """plano.json validado, ou None se não existe ou não tem nada utilizável.
    Campos inválidos são ignorados (nunca derrubam o painel)."""
    cam = os.path.join(pasta, ARQUIVO)
    try:
        if os.path.getsize(cam) > LIMITE_BYTES:
            return None
        with open(cam, encoding="utf-8-sig") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    out = {"inicio": _data(d.get("inicio")), "prova": None, "marcos": [], "ciclos": [], "selos": {}}
    p = d.get("prova")
    if isinstance(p, dict):
        data = _data(p.get("data"))
        dist = _num(p.get("dist_km"), 0, 100)
        if data and dist:
            alt = p.get("altitude_km")
            alt = ([float(x) for x in alt] if isinstance(alt, list) and len(alt) == int(round(dist)) + 1
                   and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in alt) else None)
            out["prova"] = {"nome": str(p.get("nome") or "Prova")[:80], "data": data, "dist_km": dist,
                            "meta_min": _num(p.get("meta_min"), 0, 1000), "altitude_km": alt}
    for m in (d.get("marcos") or [])[:40]:
        if isinstance(m, dict) and _data(m.get("data")):
            out["marcos"].append({"data": _data(m["data"]), "marco": str(m.get("marco") or "")[:60],
                                  "meta_min": _num(m.get("meta_min"), 0, 1000)})
    out["marcos"].sort(key=lambda m: m["data"])
    for c in (d.get("ciclos") or [])[:120]:
        if isinstance(c, dict) and _data(c.get("inicio")) and _data(c.get("fim")):
            out["ciclos"].append({"ciclo": int(c["ciclo"]) if isinstance(c.get("ciclo"), int) else len(out["ciclos"]) + 1,
                                  "inicio": _data(c["inicio"]), "fim": _data(c["fim"]),
                                  "fase": str(c.get("fase") or "")[:30], "teste": _data(c.get("teste"))})
    s = d.get("selos")
    if isinstance(s, dict):
        for k in ("longao_km", "equiv_10k_min", "ritmo_s", "ciclo_km"):
            v = s.get(k)
            if isinstance(v, list):
                out["selos"][k] = [float(x) for x in v[:12]
                                   if isinstance(x, (int, float)) and not isinstance(x, bool) and 0 < x < 100000]
    if not (out["prova"] or out["ciclos"]):
        return None
    return out


# ------------------------------------------------------------ Riegel -------
def riegel(dist_m, dur_s, alvo_m):
    return dur_s * (alvo_m / dist_m) ** EXPOENTE


def equivalentes(historico, alvo_m=10000):
    """[(data, equivalente_em_s, atividade)] das corridas de 5 km ou mais."""
    out = []
    for a in historico:
        if eh_corrida(a) and a.get("data") and (a.get("dist_m") or 0) >= MIN_EQUIV_M and (a.get("dur_s") or 0) > 0:
            out.append((a["data"], riegel(a["dist_m"], a["dur_s"], alvo_m), a))
    return out


def equivalente_de(a, alvo_m=10000):
    if eh_corrida(a) and (a.get("dist_m") or 0) >= MIN_EQUIV_M and (a.get("dur_s") or 0) > 0:
        return riegel(a["dist_m"], a["dur_s"], alvo_m)
    return None


def melhor_equivalente(historico, desde=None, ate=None):
    """(equivalente_s, data, atividade) do menor equivalente no intervalo, ou None."""
    c = [e for e in equivalentes(historico)
         if (desde is None or e[0] >= desde.isoformat()) and (ate is None or e[0] <= ate.isoformat())]
    if not c:
        return None
    e = min(c, key=lambda x: x[1])
    return e[1], e[0], e[2]


# ------------------------------------------------------ meta e contagem ----
def mmss_min(m):
    s = int(round(m * 60))
    return f"{s // 60}:{s % 60:02d}" if s < 3600 else hms(s)


def contagem(plano, historico, hoje):
    """Dados do cartão 'Rumo à prova' ou None."""
    p = plano and plano["prova"]
    if not p:
        return None
    dias = (p["data"] - hoje).days
    meta_s = p["meta_min"] * 60 if p["meta_min"] else None
    atual = melhor_equivalente(historico, hoje - dt.timedelta(days=JANELA_EQUIV_DIAS), hoje)
    inicio = None
    if plano["inicio"]:
        # ponto de partida: melhor equivalente dos 60 dias até o início do plano; se não
        # houver, o primeiro dentro dos 60 dias depois dele
        inicio = melhor_equivalente(historico, plano["inicio"] - dt.timedelta(days=JANELA_EQUIV_DIAS), plano["inicio"])
        if inicio is None:
            inicio = melhor_equivalente(historico, plano["inicio"], plano["inicio"] + dt.timedelta(days=JANELA_EQUIV_DIAS))
    frac = None
    if atual and inicio and meta_s and inicio[0] > meta_s:
        frac = max(0.0, min(1.0, (inicio[0] - atual[0]) / (inicio[0] - meta_s)))
    return {"nome": p["nome"], "data": p["data"], "dias": dias, "dist_km": p["dist_km"], "meta_s": meta_s,
            "atual": atual, "inicio": inicio, "frac": frac,
            "prova_10k": abs(p["dist_km"] - 10) < 0.01}


# ------------------------------------------------------------- ciclos ------
def ciclos(plano, historico, hoje):
    """Cada ciclo com a distância corrida (Garmin), a situação e a fase."""
    out = []
    for c in plano["ciclos"] if plano else []:
        if hoje < c["inicio"]:
            situ, d = "futuro", None
        else:
            situ = "atual" if hoje <= c["fim"] else "concluído"
            d = sum(a["dist_m"] for a in historico
                    if eh_corrida(a) and a.get("data") and a.get("dist_m")
                    and c["inicio"].isoformat() <= a["data"] <= c["fim"].isoformat()) / 1000
        out.append(dict(c, km=d, situacao=situ))
    return out


# -------------------------------------------------------------- selos ------
def _fmt_km(x):
    return f"{num(x, 1)} km"


def selos(plano, historico, cicl, hoje):
    """Lista de selos com progresso e a data da conquista (tudo calculado da Garmin).
    Cada selo: {id, nome, desc, feito, data, pct, falta}."""
    cs = sorted((a for a in historico if eh_corrida(a) and a.get("data") and a.get("dist_m")),
                key=lambda a: (a["data"], a.get("hora") or ""))
    cfg = (plano or {}).get("selos") or {}
    out = []

    def add(id_, nome, desc, valor, meta, data, falta_fmt, menor_melhor=False, pct=None):
        feito = valor is not None and (valor <= meta if menor_melhor else valor >= meta)
        if pct is None:
            pct = (0 if valor is None else 1 if feito else
                   max(0.0, min(1.0, valor / meta)) if not menor_melhor else 0)
        out.append({"id": id_, "nome": nome, "desc": desc, "feito": feito, "data": data if feito else None,
                    "pct": 1.0 if feito else pct, "falta": "" if feito or valor is None else falta_fmt(valor, meta)})

    add("r1", "Primeira corrida", "Uma corrida registrada pela Garmin", len(cs), 1,
        cs[0]["data"] if cs else None, lambda v, m: "")
    maxkm = max((a["dist_m"] for a in cs), default=0) / 1000
    for g in cfg.get("longao_km", [10, 15, 21]):
        d = next((a["data"] for a in cs if a["dist_m"] / 1000 >= g - 0.05), None)
        add(f"l{g:g}", f"Corrida de {num(g)} km", f"Uma corrida de {num(g)} km ou mais", maxkm, g, d,
            lambda v, m: f"faltam {_fmt_km(m - v)}")
    acc, datas = 0.0, {}
    for a in cs:
        acc += a["dist_m"] / 1000
        for g in (100, 250, 500, 1000):
            if acc >= g and g not in datas:
                datas[g] = a["data"]
    for g in (100, 250, 500, 1000):
        add(f"a{g}", f"{g} km no total", "Soma das corridas no histórico guardado", acc, g, datas.get(g),
            lambda v, m: f"faltam {_fmt_km(m - v)}")
    ok = [c for c in cicl if c["km"] is not None]
    for g in cfg.get("ciclo_km", []):
        if cicl:
            f = next((c for c in ok if c["km"] >= g), None)
            best = max((c["km"] for c in ok), default=0)
            add(f"c{g:g}", f"Ciclo de {num(g)} km", f"Um ciclo do plano com {num(g)} km ou mais", best, g,
                f and min(c["fim"], hoje).isoformat(), lambda v, m: f"faltam {_fmt_km(m - v)}")
    rapidas = [(a, a["dist_m"] / a["dur_s"]) for a in cs if a["dist_m"] >= MIN_EQUIV_M and a.get("dur_s")]
    for g in cfg.get("ritmo_s", []):
        melhor = min((1000 / v for _, v in rapidas), default=None)
        d = next((a["data"] for a, v in rapidas if 1000 / v <= g), None)
        add(f"p{g:g}", f"Ritmo {pace(g).replace(' /km', '')}", "Média desse ritmo, ou melhor, numa corrida de 5 km ou mais",
            melhor, g, d, lambda v, m: f"melhor: {pace(v)}", menor_melhor=True,
            pct=0 if melhor is None else max(0.0, min(1.0, g / melhor)))
    eqs = sorted(equivalentes(historico), key=lambda e: e[0])
    for g in cfg.get("equiv_10k_min", []):
        melhor = min((e[1] for e in eqs), default=None)
        d = next((e[0] for e in eqs if e[1] <= g * 60), None)
        add(f"e{g:g}", f"Equivalente abaixo de {mmss_min(g)}", "Equivalente em 10 km (Riegel) de uma corrida de 5 km ou mais",
            melhor, g * 60, d, lambda v, m: f"menor: {hms(v)}", menor_melhor=True,
            pct=0 if melhor is None else max(0.0, min(1.0, (g * 60) / melhor)))
    return out


# --------------------------------------------------------- ritmo / cor -----
ZONAS_RITMO = [  # (limite sobre o ritmo de referência, classe, rótulo)
    (1.00, "z4", "ritmo de prova ou mais rápido"),
    (1.10, "z3", "forte"),
    (1.25, "z2", "moderado"),
    (99.0, "z1", "fácil"),
]


def zona_ritmo(pace_s, ref_pace_s):
    """Classe de cor pelo ritmo comparado ao ritmo de 10 km do melhor equivalente."""
    if not pace_s or not ref_pace_s:
        return None
    r = pace_s / ref_pace_s
    for lim, cl, rot in ZONAS_RITMO:
        if r <= lim:
            return cl, rot
    return None


# ------------------------------------------------------- plano de prova ----
def _custo(g):   # Minetti 2002: custo energético por inclinação (g = subida/distância)
    return 155.4 * g ** 5 - 30.4 * g ** 4 - 43.3 * g ** 3 + 46.3 * g ** 2 + 19.5 * g + 3.6


def previsao_s(base_10k_s, dist_km):
    return base_10k_s * (dist_km / 10) ** EXPOENTE


def plano_km(tempo_s, dist_km, altitude_km=None):
    """Passagens km a km. Ritmo uniforme; com altitude (um valor por km) ajusta pelo relevo.
    Devolve [{km, dist (km do trecho), dz (m ou None), t, acum}]."""
    n = int(dist_km)
    trechos = [1.0] * n
    if dist_km - n > 1e-9:
        trechos.append(dist_km - n)
    fatores, dzs = [], []
    for i, d in enumerate(trechos):
        dz = None
        f = 1.0
        if altitude_km and i + 1 < len(altitude_km) and d == 1.0:
            dz = altitude_km[i + 1] - altitude_km[i]
            g = dz / 1000
            f = _custo(g) / _custo(0)
            if g < 0:
                f = 1 + RESTO_DESCIDA * (f - 1)
        fatores.append(f * d)
        dzs.append(dz)
    soma = sum(fatores)
    out, acum = [], 0.0
    for i, d in enumerate(trechos):
        t = tempo_s * fatores[i] / soma
        acum += t
        out.append({"km": i + 1, "dist": d, "dz": dzs[i], "t": t, "acum": acum})
    return out


def blocos_plano(plano, historico, hoje):
    """Opções do plano de prova: para cada distância, o tempo previsto e as passagens."""
    atual = melhor_equivalente(historico, hoje - dt.timedelta(days=JANELA_EQUIV_DIAS), hoje)
    meta = plano and plano["prova"] and plano["prova"]
    out = []
    for d in DISTANCIAS_PLANO:
        dk = DIST_EXATA.get(d, float(d))
        opcoes = []
        if atual:
            opcoes.append(("Previsão de hoje", previsao_s(atual[0], dk)))
        if meta and meta["meta_min"] and abs(meta["dist_km"] - dk) < 0.5:
            opcoes.append((f"Meta da prova ({mmss_min(meta['meta_min'])})", meta["meta_min"] * 60))
        alt = meta["altitude_km"] if meta and abs(meta["dist_km"] - dk) < 0.5 else None
        out.append({"dist": d, "dist_km": dk, "alt": bool(alt),
                    "opcoes": [(n, t, plano_km(t, dk, alt)) for n, t in opcoes]})
    return {"base": atual, "blocos": out}

"""Formatação de números, semanas e agrupamento de esportes (sem rede)."""
import datetime as dt

SEM_DADO = "sem dado"
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

# Esportes: (chave, rótulo, cor). Cores escolhidas para se distinguirem também
# em daltonismo (paleta Okabe-Ito adaptada ao fundo escuro) e SEM amarelo/ouro,
# que é reservado para marcar atenção (meta, média, hoje).
ESPORTES = [
    ("corrida", "Corrida", "#56B4E9"),
    ("ciclismo", "Ciclismo", "#E4572E"),
    ("natacao", "Natação", "#22A07A"),
    ("forca", "Musculação", "#CC79A7"),
    ("caminhada", "Caminhada", "#9AA7C0"),
    ("outros", "Outros", "#7D8294"),
]
_ROTULO = {k: r for k, r, _ in ESPORTES}
_COR = {k: c for k, _, c in ESPORTES}


def grupo(tipo):
    t = (tipo or "").lower()
    if "running" in t:
        return "corrida"
    if "cycling" in t or "biking" in t:
        return "ciclismo"
    if "swimming" in t:
        return "natacao"
    if "strength" in t or "weight" in t:
        return "forca"
    if "walking" in t or "hiking" in t:
        return "caminhada"
    return "outros"


def rotulo_esporte(chave):
    return _ROTULO.get(chave, chave)


def cor_esporte(chave):
    return _COR.get(chave, _COR["outros"])


def eh_corrida(a):
    return grupo(a.get("tipo")) == "corrida"


# ---------------------------------------------------------------- números --
def num(v, casas=0):
    if v is None:
        return SEM_DADO
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def km(m):
    return SEM_DADO if m is None else num(m / 1000, 2) + " km"


def hms(s):
    if s is None:
        return SEM_DADO
    s = int(round(s))
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def hm(s):
    if s is None:
        return SEM_DADO
    m = int(round(s / 60))
    return f"{m // 60} h {m % 60:02d} min"


def hcurto(s):
    """7h12 (para rótulos estreitos)."""
    if s is None:
        return ""
    m = int(round(s / 60))
    return f"{m // 60}h{m % 60:02d}"


def minutos(s):
    return SEM_DADO if s is None else f"{int(round(s / 60))} min"


def pace_de_velocidade(v):
    if not v or v <= 0:
        return None
    return 1000 / v


def pace(seg_por_km):
    if seg_por_km is None:
        return SEM_DADO
    s = int(round(seg_por_km))
    return f"{s // 60}:{s % 60:02d} /km"


def data_br(iso):
    if not iso:
        return SEM_DADO
    d = dt.date.fromisoformat(iso)
    return f"{DIAS_SEMANA[d.weekday()]} {d.day:02d}/{d.month:02d}"


# ----------------------------------------------------------------- semanas --
def segunda(d):
    return d - dt.timedelta(days=d.weekday())


def totais_semana(atividades, ini):
    fim = ini + dt.timedelta(days=6)
    cs = [a for a in atividades if eh_corrida(a) and a["data"]
          and ini.isoformat() <= a["data"] <= fim.isoformat()]
    dist = sum(a["dist_m"] for a in cs if a["dist_m"] is not None)
    dur = sum(a["dur_s"] for a in cs if a["dur_s"] is not None)
    ambos = [a for a in cs if a["dist_m"] and a["dur_s"]]
    d2 = sum(a["dist_m"] for a in ambos)
    t2 = sum(a["dur_s"] for a in ambos)
    return {"ini": ini, "fim": fim, "n": len(cs),
            "dist_m": dist if cs else 0, "dur_s": dur if cs else 0,
            "pace": (t2 / (d2 / 1000)) if d2 else None}

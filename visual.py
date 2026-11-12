"""Visual do painel: HTML + gráficos em SVG puro (sem bibliotecas externas).

Regras de dados: só usa o que a Garmin enviou. Dia sem dado fica VAZIO no
gráfico (nunca vira zero) e aparece como "sem dado" no balão e nas tabelas.
Ouro/amarelo é reservado para marcar atenção: meta de passos, média semanal
do sono e o dia de hoje / semana atual. Nenhum esporte usa essa cor.
"""
import datetime as dt
import html
import math

from formatos import (DIAS_SEMANA, ESPORTES, MELHORES, SEM_DADO, comparar_semanas, cor_esporte, data_br,
                      grupo, hcurto, hm, hms, km, minutos, num, pace,
                      pace_de_velocidade, rotulo_esporte, segunda,
                      totais_semana)

W, PL, PR, PT, PB = 1000, 58, 14, 14, 62
OPCOES = (7, 14, 30)       # períodos que o seletor oferece
PADRAO = 14
MAX_SEMANAS = 12
OURO = "#FFD23F"
ROXO = "#8B6CF4"
ROXO_CLARO = "#C4B5FD"
SONO = {"prof": ("Profundo", "#6C4BE8"), "leve": ("Leve", "#A592F5"),
        "rem": ("REM", "#E4DBFF")}
SONO_SEM_FASES = "#6F678C"
ZONAS = [("Z1", "#E4DBFF"), ("Z2", "#C4B5FD"), ("Z3", "#A592F5"),
         ("Z4", "#7C5CF0"), ("Z5", "#5B3BD6")]


def esc(x):
    return html.escape(str(x), quote=True)


# --------------------------------------------------------------- geometria --
def janela(fim, n):
    return [fim - dt.timedelta(days=n - 1 - i) for i in range(n)]


def slot(m):
    return (W - PL - PR) / m


def cx(i, m):
    return PL + slot(m) * (i + 0.5)


def larg_barra(m, frac=0.56):
    return min(slot(m) * frac, 90)


def yv(v, lo, hi, h):
    return PT + (h - PT - PB) * (1 - (v - lo) / (hi - lo))


def altura(v, lo, hi, h):
    return v / (hi - lo) * (h - PT - PB)


def escala(lo, hi, alvos=4, mults=(1, 2, 2.5, 5, 10)):
    """Limites e marcas 'redondas' para o eixo."""
    if hi <= lo:
        hi = lo + 1
    bruto = (hi - lo) / alvos
    mag = 10 ** math.floor(math.log10(bruto))
    passo = mag * 10
    for m in mults:
        if m * mag >= bruto:
            passo = m * mag
            break
    ini = math.floor(lo / passo + 1e-9) * passo
    fim = math.ceil(hi / passo - 1e-9) * passo
    marcas, t = [], ini
    while t <= fim + passo * 1e-6:
        marcas.append(t)
        t += passo
    return ini, fim, marcas


def barra(x, y, w, h, topo=True, r=5):
    r = min(r, h, w / 2) if topo else 0
    if r <= 0:
        return f"M{x:.1f},{y:.1f}h{w:.1f}v{h:.1f}h{-w:.1f}z"
    return (f"M{x:.1f},{y + h:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
            f"H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}"
            f"V{y + h:.1f}z")


def tip(titulo, *linhas):
    return "\n".join([titulo, *linhas])


def rotulos_dias(dias, hoje):
    """(linha1, linha2, destaque) por dia; None onde o rótulo é omitido."""
    n, out, primeiro = len(dias), [], True
    for i, d in enumerate(dias):
        if n > 16 and (n - 1 - i) % 2:
            out.append(None)
            continue
        rot = f"{d.day:02d}/{d.month:02d}" if (d.day == 1 or primeiro) else f"{d.day:02d}"
        primeiro = False
        out.append((DIAS_SEMANA[d.weekday()], rot, d == hoje))
    return out


def moldura(h, lo, hi, marcas, fmt, rotulos, valores):
    """Grade, eixo Y, datas e linha de valores sob cada coluna."""
    m = len(rotulos)
    out = []
    for t in marcas:
        y = yv(t, lo, hi, h)
        out.append(f'<line class="gl" x1="{PL}" x2="{W - PR}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="yl" x="{PL - 8}" y="{y + 4:.1f}" text-anchor="end">{esc(fmt(t))}</text>')
    yb = h - PB
    for i, r in enumerate(rotulos):
        if r is None:
            continue
        cl = "xl hoje" if r[2] else "xl"
        out.append(f'<text class="{cl}" x="{cx(i, m):.1f}" y="{yb + 16}" text-anchor="middle">{esc(r[0])}</text>')
        out.append(f'<text class="{cl}" x="{cx(i, m):.1f}" y="{yb + 29}" text-anchor="middle">{esc(r[1])}</text>')
        if valores[i]:
            out.append(f'<text class="vl" x="{cx(i, m):.1f}" y="{yb + 47}" text-anchor="middle">{esc(valores[i])}</text>')
    return "".join(out)


def zonas(h, tips):
    """Retângulos invisíveis, um por coluna, que mostram o balão ao passar o mouse."""
    m = len(tips)
    return "".join(
        f'<rect class="hit" x="{PL + slot(m) * i:.1f}" y="{PT}" width="{slot(m):.1f}" '
        f'height="{h - PT - 2}" data-tip="{esc(t)}"/>' for i, t in enumerate(tips))


def svg(h, corpo, rotulo, defs=""):
    return (f'<svg class="ch" viewBox="0 0 {W} {h}" role="img" '
            f'aria-label="{esc(rotulo)}"><defs>{defs}</defs>{corpo}</svg>')


def cartao(titulo, sub, corpo, extra=""):
    return (f'<section class="card {extra}"><h2>{esc(titulo)}</h2>'
            f'<p class="sub">{esc(sub)}</p>{corpo}</section>')


def chip(cor, texto, estilo="quad"):
    return (f'<span class="chip"><i class="{estilo}" style="--c:{cor}"></i>'
            f'{esc(texto)}</span>')


# ---------------------------------------------------------- gráfico: anel --
def graf_anel(acts, ini_sem, fim_sem):
    por = {}
    for a in acts:
        if a["data"] and ini_sem.isoformat() <= a["data"] <= fim_sem.isoformat():
            e = por.setdefault(grupo(a["tipo"]), {"dur": 0, "dist": 0, "n": 0})
            e["n"] += 1
            e["dur"] += a["dur_s"] or 0
            e["dist"] += a["dist_m"] or 0
    segs = [(k, por[k]) for k, _, _ in ESPORTES if k in por and por[k]["dur"] > 0]
    total = sum(e["dur"] for _, e in segs)
    r, ct = 96, 130
    circ = 2 * math.pi * r
    corpo = [f'<circle cx="{ct}" cy="{ct}" r="{r}" fill="none" stroke="rgba(167,139,250,.14)" stroke-width="30"/>']
    leg = []
    acc = 0.0
    for k, e in segs:
        ln = e["dur"] / total * circ
        gap = 3 if len(segs) > 1 else 0
        t = tip(rotulo_esporte(k), f"Tempo|{hms(e['dur'])}",
                f"Atividades|{e['n']}", f"Distância|{km(e['dist'] or None)}")
        corpo.append(
            f'<circle class="seg" cx="{ct}" cy="{ct}" r="{r}" fill="none" '
            f'stroke="{cor_esporte(k)}" stroke-width="30" '
            f'stroke-dasharray="{max(ln - gap, 0.01):.2f} {circ:.2f}" '
            f'stroke-dashoffset="{-acc:.2f}" transform="rotate(-90 {ct} {ct})" '
            f'data-tip="{esc(t)}"/>')
        acc += ln
        leg.append(
            f'<li><i class="quad" style="--c:{cor_esporte(k)}"></i>'
            f'<span class="nm">{esc(rotulo_esporte(k))}</span>'
            f'<span class="n">{esc(hms(e["dur"]))}</span>'
            f'<span class="n mut">{round(e["dur"] / total * 100)}%</span></li>')
    if segs:
        corpo.append(f'<text class="rg" x="{ct}" y="{ct + 4}" text-anchor="middle">{esc(hms(total))}</text>')
        corpo.append(f'<text class="rs" x="{ct}" y="{ct + 26}" text-anchor="middle">tempo total</text>')
    else:
        corpo.append(f'<text class="rs" x="{ct}" y="{ct + 4}" text-anchor="middle">sem atividades</text>')
        leg.append('<li class="mut">Nenhuma atividade nesta semana.</li>')
    anel = (f'<svg class="anel" viewBox="0 0 260 260" role="img" '
            f'aria-label="Tempo por esporte na semana">{"".join(corpo)}</svg>')
    return f'<div class="anelbox">{anel}<ul class="leg">{"".join(leg)}</ul></div>'


# ------------------------------------------------ gráfico: treino por dia ---
def graf_treino(dias, acts, hoje):
    m = len(dias)
    por = {d.isoformat(): {} for d in dias}
    com_ativ = set()
    for a in acts:
        k = a["data"]
        if k in por:
            com_ativ.add(k)
            e = por[k].setdefault(grupo(a["tipo"]), {"dur": 0, "dist": 0, "n": 0, "tem": False})
            e["n"] += 1
            if a["dur_s"] is not None:
                e["dur"] += a["dur_s"]
                e["tem"] = True
            e["dist"] += a["dist_m"] or 0
    totais = [sum(e["dur"] for e in por[d.isoformat()].values()) for d in dias]
    h = 320
    lo, hi, marcas = escala(0, max(max(totais) / 60, 30), 4)
    corpo, tips, valores, usados = [], [], [], set()
    bw = larg_barra(m)
    y_base = yv(0, lo, hi, h)
    ordem = [x[0] for x in ESPORTES]
    for i, d in enumerate(dias):
        k = d.isoformat()
        segs = [(g_, por[k][g_]) for g_, _, _ in ESPORTES if g_ in por[k] and por[k][g_]["dur"] > 0]
        acc = 0.0
        for j, (g_, e) in enumerate(segs):
            usados.add(g_)
            alt = altura(e["dur"] / 60, lo, hi, h)
            corpo.append(f'<path class="sep" d="{barra(cx(i, m) - bw / 2, y_base - acc - alt, bw, alt, j == len(segs) - 1)}" '
                         f'fill="{cor_esporte(g_)}"/>')
            acc += alt
        if k not in com_ativ:
            corpo.append(f'<text class="desc" transform="translate({cx(i, m) + 4:.1f},{y_base - 8:.1f}) rotate(-90)">descanso</text>')
            tips.append(tip(data_br(k), "descanso"))
            valores.append("")
        else:
            linhas = [f"{rotulo_esporte(g_)}|{minutos(e['dur']) if e['tem'] else SEM_DADO}"
                      + (f" · {km(e['dist'])}" if e["dist"] else "")
                      for g_, e in sorted(por[k].items(), key=lambda kv: ordem.index(kv[0]))]
            tips.append(tip(data_br(k), *linhas, f"Total|{minutos(totais[i]) if totais[i] else SEM_DADO}"))
            valores.append(f"{round(totais[i] / 60)} min" if totais[i] else "")
    leg = "".join(chip(cor_esporte(g_), rotulo_esporte(g_)) for g_, _, _ in ESPORTES if g_ in usados)
    if m > 16:
        valores = [""] * m
    base = moldura(h, lo, hi, marcas, lambda t: f"{t:g}", rotulos_dias(dias, hoje), valores)
    return (f'<div class="legrow">{leg}<span class="mut">minutos de treino por dia</span></div>'
            + svg(h, base + "".join(corpo) + zonas(h, tips), "Tempo de treino por dia, colorido por esporte"))


# ------------------------------------------------------- gráfico: sono ------
def graf_sono(dias, todos, hoje):
    m = len(dias)
    por = {d["data"]: d for d in todos}
    noites = [por.get(d.isoformat(), {}) for d in dias]
    if not any(n.get("sono_s") for n in noites):
        return None
    totais = [n.get("sono_s") for n in noites]
    h = 320
    lo, hi, marcas = escala(0, max(t for t in totais if t) / 3600, 4, mults=(1, 2, 5, 10))
    corpo, tips, valores = [], [], []
    bw = larg_barra(m)
    y_base = yv(0, lo, hi, h)
    for i, d in enumerate(dias):
        n, k = noites[i], d.isoformat()
        if not n.get("sono_s"):
            tips.append(tip(data_br(k), "Sono|sem dado"))
            valores.append("")
            continue
        fases = [(c_, n.get(f"sono_{c_}_s")) for c_ in ("prof", "leve", "rem")]
        presentes = [(c_, v) for c_, v in fases if v]
        acc = 0.0
        if not presentes:
            alt = altura(n["sono_s"] / 3600, lo, hi, h)
            corpo.append(f'<path d="{barra(cx(i, m) - bw / 2, y_base - alt, bw, alt)}" fill="{SONO_SEM_FASES}"/>')
        for j, (c_, v) in enumerate(presentes):
            alt = altura(v / 3600, lo, hi, h)
            corpo.append(f'<path class="sep" d="{barra(cx(i, m) - bw / 2, y_base - acc - alt, bw, alt, j == len(presentes) - 1)}" '
                         f'fill="{SONO[c_][1]}"/>')
            acc += alt
        tips.append(tip(data_br(k), *[f"{SONO[c_][0]}|{hm(v) if v else SEM_DADO}" for c_, v in fases],
                        f"Total|{hm(n['sono_s'])}"))
        valores.append(hcurto(n["sono_s"]))
    # média da semana (segunda a domingo), com todas as noites da semana
    semanas = {}
    for d in todos:
        if d.get("sono_s"):
            semanas.setdefault(segunda(dt.date.fromisoformat(d["data"])), []).append(d["sono_s"])
    linhas_media, resumo = [], []
    for ini_s in sorted(semanas):
        idx = [i for i, d in enumerate(dias) if segunda(d) == ini_s]
        if not idx:
            continue
        media = sum(semanas[ini_s]) / len(semanas[ini_s])
        y = yv(media / 3600, lo, hi, h)
        x1, x2 = PL + slot(m) * idx[0] + 3, PL + slot(m) * (idx[-1] + 1) - 3
        linhas_media.append(f'<line class="avg" x1="{x1:.1f}" x2="{x2:.1f}" y1="{y:.1f}" y2="{y:.1f}"/>')
        fim_s = ini_s + dt.timedelta(days=6)
        resumo.append(f'<li><i class="trac"></i>Semana {ini_s.day:02d}/{ini_s.month:02d} a '
                      f'{fim_s.day:02d}/{fim_s.month:02d}: <b>{esc(hm(media))}</b> '
                      f'<span class="mut">({len(semanas[ini_s])} noites com dado)</span></li>')
    leg = "".join(chip(c_, n_) for n_, c_ in SONO.values()) + \
        '<span class="chip"><i class="trac"></i>média da semana</span>'
    if m > 16:
        valores = [""] * m
    base = moldura(h, lo, hi, marcas, lambda t: f"{t:g}h", rotulos_dias(dias, hoje), valores)
    return (f'<div class="legrow">{leg}</div>'
            + svg(h, base + "".join(corpo) + "".join(linhas_media) + zonas(h, tips),
                  "Sono por noite: profundo, leve e REM")
            + f'<ul class="med">{"".join(resumo)}</ul>')


# ------------------------------------------------------ gráfico: passos -----
def graf_barras_meta(dias, todos, hoje, campo, campo_meta, nome, nome_meta, rotulo_aria):
    """Barras por dia com um traço dourado na meta do dia (passos, hidratação)."""
    m = len(dias)
    por = {d["data"]: d for d in todos}
    reg = [por.get(d.isoformat(), {}) for d in dias]
    if not any(r.get(campo) for r in reg):
        return None
    h = 320
    topo = max([r.get(campo) or 0 for r in reg] + [r.get(campo_meta) or 0 for r in reg])
    lo, hi, marcas = escala(0, topo, 4)
    corpo, tips, valores = [], [], []
    bw = larg_barra(m)
    y0 = yv(0, lo, hi, h)
    tem_meta = False
    for i, d in enumerate(dias):
        r, k = reg[i], d.isoformat()
        p, mt = r.get(campo), r.get(campo_meta)
        if p:
            corpo.append(f'<path d="{barra(cx(i, m) - bw / 2, y0 - altura(p, lo, hi, h), bw, altura(p, lo, hi, h))}" fill="{ROXO}"/>')
        if mt:
            tem_meta = True
            y = yv(mt, lo, hi, h)
            corpo.append(f'<line class="meta" x1="{cx(i, m) - bw / 2 - 5:.1f}" x2="{cx(i, m) + bw / 2 + 5:.1f}" y1="{y:.1f}" y2="{y:.1f}"/>')
        tips.append(tip(data_br(k), f"{nome}|{num(p) if p else SEM_DADO}",
                        f"{nome_meta}|{num(mt) if mt else SEM_DADO}"))
        valores.append(num(p) if p and m <= 16 else "")
    leg = chip(ROXO, nome.lower()) + (
        f'<span class="chip"><i class="traco"></i>{esc(nome_meta.lower())}</span>' if tem_meta else "")
    base = moldura(h, lo, hi, marcas, lambda t: num(t), rotulos_dias(dias, hoje), valores)
    return f'<div class="legrow">{leg}</div>' + svg(h, base + "".join(corpo) + zonas(h, tips), rotulo_aria)


def graf_passos(dias, todos, hoje):
    return graf_barras_meta(dias, todos, hoje, "passos", "meta_passos", "Passos",
                            "Meta da Garmin", "Passos por dia e meta")


def graf_hidratacao(dias, todos, hoje):
    return graf_barras_meta(dias, todos, hoje, "hidrat_ml", "meta_hidrat_ml", "Hidratação (ml)",
                            "Meta de hidratação", "Hidratação por dia e meta")


# ------------------------------------------------- gráfico: body battery ----
def graf_bb(dias, todos, hoje):
    m = len(dias)
    por = {d["data"]: d for d in todos}
    reg = [por.get(d.isoformat(), {}) for d in dias]
    if not any(r.get("bb_min") is not None and r.get("bb_max") is not None for r in reg):
        return None
    h = 300
    lo, hi, marcas = 0, 100, [0, 25, 50, 75, 100]
    corpo, tips, valores = [], [], []
    bw = larg_barra(m, 0.44)
    for i, d in enumerate(dias):
        r, k = reg[i], d.isoformat()
        a, b = r.get("bb_min"), r.get("bb_max")
        if a is None or b is None:
            tips.append(tip(data_br(k), "Body Battery|sem dado"))
            valores.append("")
            continue
        y1, y2 = yv(b, lo, hi, h), yv(a, lo, hi, h)
        corpo.append(f'<rect x="{cx(i, m) - bw / 2:.1f}" y="{y1:.1f}" width="{bw:.1f}" '
                     f'height="{max(y2 - y1, 5):.1f}" rx="{min(7, bw / 2):.1f}" fill="url(#gbb)"/>')
        tips.append(tip(data_br(k), f"Máximo|{b}", f"Mínimo|{a}"))
        valores.append(f"{a}–{b}" if m <= 16 else "")
    defs = (f'<linearGradient id="gbb" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{ROXO_CLARO}"/><stop offset="1" stop-color="{ROXO}"/></linearGradient>')
    base = moldura(h, lo, hi, marcas, lambda t: f"{t:g}", rotulos_dias(dias, hoje), valores)
    return svg(h, base + "".join(corpo) + zonas(h, tips), "Body Battery: mínimo e máximo de cada dia", defs)


# ----------------------------------------------- gráficos de linha ---------
def graf_linha(dias, todos, hoje, campo, unidade, nome, casas=0, pad_min=4):
    m = len(dias)
    por = {d["data"]: d for d in todos}
    vals = [por.get(d.isoformat(), {}).get(campo) for d in dias]
    if not any(v is not None for v in vals):
        return None
    h = 280
    presentes = [v for v in vals if v is not None]
    vmin, vmax = min(presentes), max(presentes)
    pad = max((vmax - vmin) * 0.3, pad_min)
    lo, hi, marcas = escala(vmin - pad, vmax + pad, 4)
    corpo, tips, valores = [], [], []
    pontos = [(cx(i, m), yv(v, lo, hi, h)) if v is not None else None for i, v in enumerate(vals)]
    trecho = []
    for p in pontos + [None]:
        if p is not None:
            trecho.append(p)
            continue
        if len(trecho) > 1:
            d_ = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in trecho)
            corpo.append(f'<path d="{d_}" fill="none" stroke="{ROXO}" stroke-width="2.5" stroke-linejoin="round"/>')
        trecho = []
    for i, p in enumerate(pontos):
        k = dias[i].isoformat()
        if p is None:
            tips.append(tip(data_br(k), f"{nome}|sem dado"))
            valores.append("")
        else:
            corpo.append(f'<circle class="sep" cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="5" fill="{ROXO_CLARO}"/>')
            tips.append(tip(data_br(k), f"{nome}|{num(vals[i], casas)} {unidade}"))
            valores.append(num(vals[i], casas) if m <= 16 else "")
    base = moldura(h, lo, hi, marcas, lambda t: num(t, casas), rotulos_dias(dias, hoje), valores)
    return svg(h, base + "".join(corpo) + zonas(h, tips), f"{nome} por dia")


# ------------------------------------------- gráficos por semana (novos) ---
def semanas_lista(ini, hoje):
    s, out = segunda(hoje), []
    while s >= segunda(ini) and len(out) < MAX_SEMANAS:
        out.append(s)
        s -= dt.timedelta(days=7)
    return list(reversed(out))


def _rot_sem(semanas, hoje):
    return [("sem", f"{s.day:02d}/{s.month:02d}", s == segunda(hoje)) for s in semanas]


def graf_dist_semana(atividades, ini, hoje):
    semanas = semanas_lista(ini, hoje)
    tots = [totais_semana(atividades, s) for s in semanas]
    if not any(t["n"] for t in tots):
        return None
    m, h = len(semanas), 300
    lo, hi, marcas = escala(0, max(t["dist_m"] for t in tots) / 1000, 4)
    corpo, tips, valores = [], [], []
    bw = larg_barra(m, 0.5)
    y0 = yv(0, lo, hi, h)
    for i, t in enumerate(tots):
        titulo = f"Semana {t['ini'].day:02d}/{t['ini'].month:02d} a {t['fim'].day:02d}/{t['fim'].month:02d}"
        if t["n"]:
            alt = altura(t["dist_m"] / 1000, lo, hi, h)
            corpo.append(f'<path d="{barra(cx(i, m) - bw / 2, y0 - alt, bw, alt)}" fill="{cor_esporte("corrida")}"/>')
            tips.append(tip(titulo, f"Distância|{km(t['dist_m'])}", f"Corridas|{t['n']}",
                            f"Tempo|{hms(t['dur_s'])}", f"Pace médio|{pace(t['pace'])}"))
            valores.append(f"{num(t['dist_m'] / 1000, 1)} km")
        else:
            tips.append(tip(titulo, "Corridas|0"))
            valores.append("")
    base = moldura(h, lo, hi, marcas, lambda t: num(t), _rot_sem(semanas, hoje), valores)
    leg = chip(cor_esporte("corrida"), "distância de corrida") + \
        '<span class="mut">quilômetros por semana (segunda a domingo); a semana em dourado ainda está em andamento</span>'
    return (f'<div class="legrow">{leg}</div>'
            + svg(h, base + "".join(corpo) + zonas(h, tips), "Distância de corrida por semana"))


def graf_zonas_semana(atividades, ini, hoje):
    semanas = semanas_lista(ini, hoje)
    por = []
    for s in semanas:
        a, b = s.isoformat(), (s + dt.timedelta(days=6)).isoformat()
        z = [0.0] * 5
        tem = False
        for x in atividades:
            if x.get("zonas") and x["data"] and a <= x["data"] <= b:
                tem = True
                for k, v in enumerate(x["zonas"]):
                    z[k] += v or 0
        por.append(z if tem else None)
    if not any(por):
        return None
    m, h = len(semanas), 300
    totais = [sum(z) if z else 0 for z in por]
    lo, hi, marcas = escala(0, max(max(totais) / 60, 30), 4)
    corpo, tips, valores = [], [], []
    bw = larg_barra(m, 0.5)
    y0 = yv(0, lo, hi, h)
    for i, s in enumerate(semanas):
        titulo = f"Semana {s.day:02d}/{s.month:02d} a {(s + dt.timedelta(days=6)).day:02d}/{(s + dt.timedelta(days=6)).month:02d}"
        z = por[i]
        if not z:
            tips.append(tip(titulo, "Zonas de FC|sem dado"))
            valores.append("")
            continue
        acc = 0.0
        usadas = [k for k in range(5) if z[k] > 0]
        for j, k in enumerate(usadas):
            alt = altura(z[k] / 60, lo, hi, h)
            corpo.append(f'<path class="sep" d="{barra(cx(i, m) - bw / 2, y0 - acc - alt, bw, alt, j == len(usadas) - 1)}" fill="{ZONAS[k][1]}"/>')
            acc += alt
        tips.append(tip(titulo, *[f"{ZONAS[k][0]}|{hms(z[k])}" for k in range(5)],
                        f"Total|{hms(sum(z))}"))
        valores.append(f"{round(sum(z) / 60)} min")
    base = moldura(h, lo, hi, marcas, lambda t: f"{t:g}", _rot_sem(semanas, hoje), valores)
    leg = "".join(chip(c_, n_) for n_, c_ in ZONAS) + \
        '<span class="mut">minutos por zona de FC, atividades com dado de zona</span>'
    return (f'<div class="legrow">{leg}</div>'
            + svg(h, base + "".join(corpo) + zonas(h, tips), "Tempo em cada zona de frequência cardíaca por semana"))


# --------------------------------------------------------------- tabelas ----
def _cel(i, x, esq):
    ordem = ""
    if isinstance(x, tuple):
        x, ordem = x
        ordem = f' data-v="{esc(ordem)}"'
    cl = ("e " if i in esq else "") + ("sd" if x == SEM_DADO else "")
    return f'<td class="{cl.strip()}"{ordem}>{esc(x)}</td>'


def tabela(nome, cabecalho, linhas, esq=(0,), datas=None):
    """Tabela ordenável (clique no título) com botão de exportar CSV.
    Cada célula pode ser texto ou (texto, valor_para_ordenar)."""
    h = "".join(f'<th class="ord{" e" if i in esq else ""}" tabindex="0" role="button" '
                f'aria-label="Ordenar por {esc(x)}">{esc(x)}</th>'
                for i, x in enumerate(cabecalho))
    corpo = []
    for n, l in enumerate(linhas):
        d = f' data-d="{datas[n]}"' if datas and datas[n] else ""
        corpo.append(f"<tr{d}>" + "".join(_cel(i, x, esq) for i, x in enumerate(l)) + "</tr>")
    return (f'<div class="tb"><div class="barra"><button type="button" class="csv" '
            f'data-nome="{esc(nome)}">Exportar CSV</button></div>'
            f'<div class="tw"><table data-nome="{esc(nome)}"><thead><tr>{h}</tr></thead>'
            f'<tbody>{"".join(corpo)}</tbody></table></div></div>')


def intervalo(ini, fim):
    return f"{ini.day:02d}/{ini.month:02d} a {fim.day:02d}/{fim.month:02d}"


def _min_dia(acts_por_dia, k):
    atv = acts_por_dia.get(k)
    if not atv:
        return ("descanso", 0)
    tot = [a["dur_s"] for a in atv if a["dur_s"] is not None]
    return (minutos(sum(tot)), sum(tot)) if tot else (SEM_DADO, "")


def _v(texto, valor):
    """Célula com valor de ordenação; vazio se não há dado."""
    return (texto, "" if valor is None or texto == SEM_DADO else valor)


def recordes(historico):
    """Recordes pessoais no histórico guardado (números da Garmin).
    Cada linha: [recorde, valor, detalhe, dia]."""
    corridas = [a for a in historico if grupo(a["tipo"]) == "corrida"]
    linhas = []
    for dist, rot in MELHORES:
        cand = [(a["melhores"].get(dist), a) for a in corridas
                if (a.get("melhores") or {}).get(dist)]
        if cand:
            t, a = min(cand, key=lambda c_: c_[0])
            linhas.append([f"Mais rápido: {rot}", _v(hms(t), t),
                           f"pace {pace(t / (dist / 1000))}", (data_br(a["data"]), a["data"] or "")])

    def melhor(chave, rotulo, fmt, detalhe):
        cand = [a for a in corridas if a.get(chave)]
        if cand:
            a = max(cand, key=lambda x: x[chave])
            linhas.append([rotulo, _v(fmt(a[chave]), a[chave]), detalhe(a),
                           (data_br(a["data"]), a["data"] or "")])
    melhor("dist_m", "Corrida mais longa", km,
           lambda a: f"{hms(a['dur_s'])} · pace {pace(pace_de_velocidade(a['vel_ms']))}")
    melhor("dur_s", "Corrida mais demorada", hms, lambda a: km(a["dist_m"]))
    melhor("elev_m", "Maior ganho de elevação", lambda v: f"{num(v)} m", lambda a: km(a["dist_m"]))
    semanas = {}
    for a in corridas:
        if a["data"] and a["dist_m"]:
            k = segunda(dt.date.fromisoformat(a["data"]))
            e = semanas.setdefault(k, [0.0, 0])
            e[0] += a["dist_m"]
            e[1] += 1
    if semanas:
        k, (d_, n_) = max(semanas.items(), key=lambda kv: kv[1][0])
        linhas.append(["Semana com mais distância", _v(km(d_), d_), f"{n_} corridas",
                       (f"semana de {k.day:02d}/{k.month:02d}/{k.year}", k.isoformat())])
    return linhas


def tabelas(dias, atividades, ini, hoje):
    sem0 = segunda(hoje)
    semanas, s = [], sem0
    while s >= segunda(ini):
        t = totais_semana(atividades, s)
        semanas.append([(intervalo(t["ini"], t["fim"]), s.isoformat()), t["n"],
                        _v(km(t["dist_m"]), t["dist_m"]),
                        _v(hms(t["dur_s"]) if t["n"] else SEM_DADO, t["dur_s"]),
                        _v(pace(t["pace"]), t["pace"])])
        s -= dt.timedelta(days=7)
    linhas_at, datas_at = [], []
    for a in atividades:
        g_ = grupo(a["tipo"])
        com_pace = g_ in ("corrida", "caminhada")
        pc = pace_de_velocidade(a["vel_ms"]) if com_pace else None
        linhas_at.append([
            (data_br(a["data"]), f'{a["data"] or ""} {a.get("hora") or ""}'),
            rotulo_esporte(g_) if a["tipo"] else SEM_DADO,
            a["nome"] or SEM_DADO, _v(km(a["dist_m"]), a["dist_m"]),
            _v(hms(a["dur_s"]), a["dur_s"]), _v(pace(pc), pc),
            _v(f'{num(a["fc_media"])} bpm' if a.get("fc_media") else SEM_DADO, a.get("fc_media")),
            _v(f'{num(a["cad"])} ppm' if a.get("cad") else SEM_DADO, a.get("cad")),
            _v(f'{num(a["elev_m"])} m' if a.get("elev_m") is not None else SEM_DADO, a.get("elev_m")),
            _v(num(a["vo2"]) if a.get("vo2") else SEM_DADO, a.get("vo2"))])
        datas_at.append(a["data"])
    por_dia = {}
    for a in atividades:
        if a["data"]:
            por_dia.setdefault(a["data"], []).append(a)
    linhas_d, datas_d = [], []
    for d in reversed(dias):
        def par(a, b, suf=""):
            return f"{d[a]}–{d[b]}{suf}" if d.get(a) is not None and d.get(b) is not None else SEM_DADO

        def sec(k):
            return _v(hm(d.get(k)) if d.get(k) else SEM_DADO, d.get(k))
        linhas_d.append([
            (data_br(d["data"]), d["data"]), _v(num(d.get("passos")), d.get("passos")),
            _v(num(d.get("meta_passos")), d.get("meta_passos")),
            _min_dia(por_dia, d["data"]),
            sec("sono_s"), sec("sono_prof_s"), sec("sono_leve_s"), sec("sono_rem_s"),
            _v(f'{d["fc_repouso"]} bpm' if d.get("fc_repouso") else SEM_DADO, d.get("fc_repouso")),
            _v(f'{num(d["vfc"])} ms' if d.get("vfc") else SEM_DADO, d.get("vfc")),
            par("fc_min", "fc_max", " bpm"), _v(num(d.get("estresse")), d.get("estresse")),
            _v(par("bb_min", "bb_max"), d.get("bb_max")),
            _v(num(d.get("intensidade")), d.get("intensidade")),
            _v(num(d.get("calorias")), d.get("calorias")),
            _v(num(d.get("respiracao")), d.get("respiracao")),
            _v(num(d.get("spo2")), d.get("spo2")), _v(num(d.get("andares")), d.get("andares")),
            _v(f'{num(d["peso"], 1)} kg' if d.get("peso") else SEM_DADO, d.get("peso")),
            _v(num(d.get("hidrat_ml")), d.get("hidrat_ml")),
            _v(num(d.get("meta_hidrat_ml")), d.get("meta_hidrat_ml"))])
        datas_d.append(d["data"])
    return semanas, linhas_at, datas_at, linhas_d, datas_d


# ------------------------------------- comparação de semanas e metas ----
def card_comparacao(c):
    """Esta semana x semana passada x média das últimas semanas (corridas)."""
    cols = [("Esta semana (até hoje)", c["atual"], "#C4B5FD"),
            ("Semana passada", c["passada"], "#8B6CF4")]
    if c["media"]:
        cols.append((f"Média das últimas {c['semanas_media']} semanas", c["media"], "#5B3BD6"))

    def n_txt(v):
        return num(v, 0 if abs(v - round(v)) < 1e-9 else 1)
    metricas = [("Distância", "dist_m", km, True), ("Tempo", "dur_s", hms, True),
                ("Corridas", "n", n_txt, True), ("Pace médio", "pace", pace, False)]
    html_ = [f'<div class="cmp" style="--cols:{len(cols)}"><div></div>']
    html_ += [f'<div class="cab">{esc(t)}</div>' for t, _, _ in cols]
    for rot, chave, fmt, barras in metricas:
        vals = [col[1][chave] for col in cols]
        topo = max([v for v in vals if v], default=0)
        html_.append(f'<div class="mt">{esc(rot)}</div>')
        for (_, dados, cor), v in zip(cols, vals):
            texto = fmt(v) if v is not None else SEM_DADO
            largura = f'{(v / topo * 100) if (barras and topo and v) else 0:.1f}%'
            html_.append(
                f'<div class="cel"><span class="vv{" sd" if texto == SEM_DADO else ""}">{esc(texto)}</span>'
                + (f'<i class="bar" style="width:{largura};background:{cor}"></i>' if barras else "")
                + "</div>")
    html_.append("</div>")
    nota = ('<p class="sub">Semanas de segunda a domingo; a semana atual vai até hoje. '
            'Semana sem corrida conta como 0 na média. O pace da média é o tempo total '
            'dividido pela distância total.</p>')
    return "".join(html_) + nota


def card_metas(lista):
    linhas = []
    for m in lista:
        largura = min(max(m["pct"], 0), 100)
        linhas.append(
            f'<div class="meta-lin"><div class="topo"><b>{esc(m["rotulo"])}</b>'
            f'<span class="mut">{esc(m["periodo"])}</span></div>'
            f'<div class="trilho" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
            f'aria-valuenow="{min(m["pct"], 100)}" aria-label="{esc(m["rotulo"])}">'
            f'<i class="enche" style="width:{largura}%"></i></div>'
            f'<div class="txt"><span class="vv">{esc(m["texto"])}</span>'
            f'<span class="vv pct">{m["pct"]}%</span></div></div>')
    return ('<div class="metas">' + "".join(linhas) + "</div>"
            '<p class="sub">As metas são suas (definidas por você); o realizado é a soma das corridas '
            'enviadas pela Garmin. A marca dourada é o fim da meta.</p>')


# ---------------------------------------------------------------- página ----
CSS = """
:root{--bg:#0b0813;--card:rgba(26,19,42,.78);--bd:rgba(167,139,250,.2);
--tx:#ece8f8;--mut:#a79fc2;--ouro:#FFD23F;--roxo:#8B6CF4;--roxo2:#C4B5FD;--sep:#120d1c;
--grade:rgba(167,139,250,.14);
--titulo:"Segoe UI Black","Arial Black","Verdana",sans-serif;
--mono:"Courier New","Cascadia Mono",Consolas,monospace}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;color:var(--tx);font:15px/1.45 "Segoe UI",system-ui,sans-serif;min-height:100vh;
background-color:var(--bg);
background-image:radial-gradient(900px 520px at 100% -8%,rgba(139,92,246,.32),transparent 62%),
linear-gradient(rgba(167,139,250,.05) 1px,transparent 1px),
linear-gradient(90deg,rgba(167,139,250,.05) 1px,transparent 1px);
background-size:auto,44px 44px,44px 44px;background-attachment:fixed}
main{max-width:1100px;margin:0 auto;padding:28px 16px 56px}
h1{font:900 2rem/1.1 var(--titulo);letter-spacing:.02em;margin:0 0 6px;text-transform:uppercase}
h2{font:900 1.02rem/1.2 var(--titulo);letter-spacing:.03em;margin:0 0 4px;text-transform:uppercase}
.top .sub{margin:0}.sub{color:var(--mut);font-size:.85rem;margin:0 0 12px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:18px;padding:18px 20px;margin-top:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-top:16px}
.kpi{background:var(--card);border:1px solid var(--bd);border-radius:18px;padding:16px 18px}
.kpi .r{color:var(--mut);font-size:.78rem;text-transform:uppercase;letter-spacing:.07em}
.kpi .v{font:700 2.3rem/1.15 var(--mono);color:var(--roxo2);font-variant-numeric:tabular-nums}
.kpi.s .v{font-size:1.5rem;color:var(--tx)}
.mut,.sd{color:var(--mut)}.sd{font-style:italic}
.seletor{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:18px;color:var(--mut);font-size:.85rem}
.seletor button,.csv{font:700 .8rem var(--mono);color:var(--tx);background:rgba(139,92,246,.12);
border:1px solid var(--bd);border-radius:999px;padding:6px 14px;cursor:pointer}
.seletor button:hover,.csv:hover{border-color:var(--roxo2)}
.seletor button[aria-pressed=true]{background:var(--roxo);border-color:var(--roxo2)}
button:focus-visible,th.ord:focus-visible{outline:2px solid var(--roxo2);outline-offset:2px}
.per{display:none}
.ch{width:100%;height:auto;display:block}
.ch text,.anel text{font-family:var(--mono);fill:var(--mut);font-size:11px}
.ch .xl.hoje{fill:var(--ouro);font-weight:700}.ch .vl{fill:var(--tx);font-weight:700;font-size:11px}
.ch .desc{fill:var(--mut);letter-spacing:.08em}
.anel .rg{font-size:26px;font-weight:700;fill:var(--tx)}.anel .rs{font-size:12px}
.gl{stroke:var(--grade);stroke-width:1}
.sep{stroke:var(--sep);stroke-width:1.5}
circle.sep{stroke-width:2}
.avg{stroke:var(--ouro);stroke-width:2.5;stroke-dasharray:8 5}
.meta{stroke:var(--ouro);stroke-width:3}
.hit{fill:transparent}.hit:hover{fill:rgba(167,139,250,.1)}
.seg{transition:opacity .15s}.seg:hover{opacity:.8}
.legrow{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;margin:2px 0 6px;font-size:.82rem}
.chip{display:inline-flex;align-items:center;gap:7px;color:var(--tx)}
.chip i,.leg i{display:inline-block}
i.quad{width:12px;height:12px;border-radius:3px;background:var(--c)}
i.traco{width:18px;height:0;border-top:3px solid var(--ouro)}
i.trac{width:18px;height:0;border-top:3px dashed var(--ouro);display:inline-block;margin-right:7px;vertical-align:middle}
.med{list-style:none;margin:8px 0 0;padding:0;font-size:.85rem;color:var(--tx)}
.med b{font-family:var(--mono);color:var(--tx)}
.anelbox{display:flex;flex-wrap:wrap;gap:24px;align-items:center}
.anel{width:260px;height:260px;flex:none}
.leg{list-style:none;margin:0;padding:0;flex:1;min-width:240px}
.leg li{display:grid;grid-template-columns:18px 1fr auto 52px;gap:10px;align-items:center;
padding:9px 0;border-bottom:1px solid var(--bd)}
.leg li:last-child{border-bottom:0}.leg .n{font-family:var(--mono);font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.barra{display:flex;justify-content:flex-end;margin:0 0 6px}
.tw{overflow-x:auto;background:var(--card);border:1px solid var(--bd);border-radius:18px}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{padding:9px 12px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--bd);
font-family:var(--mono);font-variant-numeric:tabular-nums}
th{color:var(--mut);font-weight:700;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;
font-family:"Segoe UI",sans-serif;cursor:pointer;user-select:none}
th.ord:hover{color:var(--tx)}th[data-ord=asc]::after{content:" ▲"}th[data-ord=desc]::after{content:" ▼"}
th.e,td.e{text-align:left}tr:last-child td{border-bottom:0}
h2.t{margin-top:30px}
.nota{color:var(--mut);font-size:.8rem;margin-top:28px}
#tip{position:fixed;z-index:9;display:none;pointer-events:none;min-width:170px;max-width:290px;
background:#1b1430;border:1px solid var(--roxo);border-radius:12px;padding:10px 12px;
box-shadow:0 10px 30px rgba(0,0,0,.5);font-size:.82rem}
#tip .th{font:900 .8rem var(--titulo);text-transform:uppercase;margin-bottom:5px;color:var(--roxo2)}
#tip .tr{display:flex;justify-content:space-between;gap:14px}
#tip .tv{font-family:var(--mono);font-weight:700;text-align:right;white-space:nowrap}
.faixa{display:flex;gap:10px;align-items:flex-start;margin-top:16px;padding:12px 16px;border-radius:14px;
border:1px solid var(--ouro);background:rgba(255,210,63,.08);color:var(--tx);font-size:.9rem}
.cmp{display:grid;grid-template-columns:120px repeat(var(--cols),1fr);gap:8px 14px;align-items:center}
.cmp .cab{color:var(--mut);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
.cmp .mt{font-weight:600}
.cmp .cel{display:flex;flex-direction:column;gap:4px}
.cmp .vv,.metas .vv{font-family:var(--mono);font-weight:700;font-variant-numeric:tabular-nums}
.cmp .bar{display:block;height:8px;border-radius:4px;min-width:2px}
.metas{display:grid;gap:16px}
.meta-lin .topo{display:flex;justify-content:space-between;gap:10px;font-size:.9rem}
.trilho{position:relative;height:12px;border-radius:6px;background:rgba(167,139,250,.16);margin:6px 0 4px;overflow:visible}
.trilho .enche{display:block;height:100%;border-radius:6px;background:var(--roxo)}
.trilho::after{content:"";position:absolute;right:-1px;top:-4px;width:3px;height:20px;border-radius:2px;background:var(--ouro)}
.meta-lin .txt{display:flex;justify-content:space-between;font-size:.9rem}
.faixa[hidden]{display:none}
.faixa b{color:var(--ouro);font-family:var(--titulo);text-transform:uppercase;font-size:.78rem;letter-spacing:.04em;white-space:nowrap}
@media (max-width:640px){.cmp{grid-template-columns:90px repeat(var(--cols),1fr);font-size:.8rem}}
@media print{
:root{--bg:#fff;--card:#fff;--bd:#c9c4d8;--tx:#1a1426;--mut:#5a5370;--ouro:#9a7400;--roxo:#6a4bd8;
--roxo2:#4b32b0;--sep:#fff;--grade:#ddd}
html,body{background:#fff!important;background-image:none!important}
.seletor,.barra,#tip,#velho{display:none!important}
.card,.kpi,.tw{break-inside:avoid;box-shadow:none}
.tw{overflow:visible}main{max-width:none;padding:0}
.ch .hit{display:none}
}
"""

JS = """
(function(){
var tip=document.getElementById('tip'),corpo=document.body;
function pinta(el){
  var L=el.getAttribute('data-tip').split('\\n');tip.textContent='';
  L.forEach(function(l,i){var d=document.createElement('div');
    if(i===0){d.className='th';d.textContent=l;}
    else{var p=l.split('|');
      if(p.length>1){d.className='tr';var a=document.createElement('span');a.textContent=p[0];
        var b=document.createElement('span');b.className='tv';b.textContent=p.slice(1).join('|');d.append(a,b);}
      else{d.textContent=l;}}
    tip.appendChild(d);});
}
function pos(x,y){
  tip.style.display='block';
  var w=tip.offsetWidth,h=tip.offsetHeight,X=x+16,Y=y+16;
  if(X+w>innerWidth-8)X=x-w-16;if(Y+h>innerHeight-8)Y=innerHeight-h-8;
  tip.style.left=Math.max(8,X)+'px';tip.style.top=Math.max(8,Y)+'px';
}
var atual=null;
function mover(e){var el=e.target.closest&&e.target.closest('[data-tip]');
  if(!el){tip.style.display='none';atual=null;return;}
  if(el!==atual){atual=el;pinta(el);} pos(e.clientX,e.clientY);}
document.addEventListener('mousemove',mover);
document.addEventListener('click',mover);
document.addEventListener('mouseleave',function(){tip.style.display='none';atual=null;});

// período dos gráficos e das tabelas diárias
function iso(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
function periodo(n){
  corpo.setAttribute('data-n',n);
  document.querySelectorAll('.seletor button').forEach(function(b){
    b.setAttribute('aria-pressed',b.getAttribute('data-n')===String(n)?'true':'false');});
  var h=corpo.getAttribute('data-hoje').split('-'),f=new Date(+h[0],+h[1]-1,+h[2]);
  f.setDate(f.getDate()-(n-1));var corte=iso(f);
  document.querySelectorAll('tr[data-d]').forEach(function(tr){tr.hidden=tr.getAttribute('data-d')<corte;});
  tip.style.display='none';
}
document.querySelectorAll('.seletor button').forEach(function(b){
  b.addEventListener('click',function(){periodo(+b.getAttribute('data-n'));});});
periodo(+corpo.getAttribute('data-n'));

// faixa de "dados velhos": compara a hora da última atualização com a hora de agora
(function(){
  var v=document.getElementById('velho'),g=corpo.getAttribute('data-gerado');
  if(!v||!g)return;
  var t=new Date(g).getTime();if(isNaN(t))return;
  var h=(Date.now()-t)/3600000;
  if(h<13)return;
  var d=Math.floor(h/24),hh=Math.floor(h%24),txt=d>0?d+(d===1?' dia':' dias')+(hh?' e '+hh+' h':''):Math.floor(h)+' h';
  v.querySelector('span').textContent='Os dados deste painel foram atualizados há '+txt+'. Use atualizar.bat para buscar dados novos (a atualização automática roda a cada 6 horas, se estiver ligada).';
  v.hidden=false;
})();

// ordenar tabelas
function valor(td){var v=td.getAttribute('data-v');
  if(v!==null){return v===''?null:(/^-?[0-9]+(\\.[0-9]+)?$/.test(v)?parseFloat(v):v);}
  var t=td.textContent.trim();if(t===''||t==='sem dado')return null;
  var n=parseFloat(t.replace(/\\./g,'').replace(',','.'));return isNaN(n)?t:n;}
function ordenar(th){
  var tab=th.closest('table'),i=[].indexOf.call(th.parentNode.children,th),
      asc=th.getAttribute('data-ord')!=='asc',tb=tab.tBodies[0],
      linhas=[].slice.call(tb.rows);
  tab.querySelectorAll('th').forEach(function(x){x.removeAttribute('data-ord');});
  th.setAttribute('data-ord',asc?'asc':'desc');
  linhas.sort(function(a,b){var x=valor(a.cells[i]),y=valor(b.cells[i]);
    if(x===null&&y===null)return 0;if(x===null)return 1;if(y===null)return -1;
    var r=(typeof x==='number'&&typeof y==='number')?x-y:String(x).localeCompare(String(y),'pt-BR',{numeric:true});
    return asc?r:-r;});
  linhas.forEach(function(r){tb.appendChild(r);});
}
document.querySelectorAll('th.ord').forEach(function(th){
  th.addEventListener('click',function(){ordenar(th);});
  th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();ordenar(th);}});});

// exportar CSV (só as linhas visíveis; "sem dado" vira vazio)
function csvCel(t){t=t.trim();if(t==='sem dado')t='';if(/^[=+@]/.test(t)||/^-[^0-9.,]/.test(t))t="'"+t;return '"'+t.replace(/"/g,'""')+'"';}
document.querySelectorAll('button.csv').forEach(function(b){
  b.addEventListener('click',function(){
    var tab=b.closest('.tb').querySelector('table'),out=[];
    [].forEach.call(tab.rows,function(tr){if(tr.hidden)return;
      out.push([].map.call(tr.cells,function(td){return csvCel(td.textContent);}).join(';'));});
    var blob=new Blob(['\\ufeff'+out.join('\\r\\n')],{type:'text/csv;charset=utf-8'}),
        a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download='painel-'+tab.getAttribute('data-nome')+'.csv';document.body.appendChild(a);
    a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(a.href);},1000);});});
})();
"""


def pagina(dias, atividades, ini, fim, agora, avisos=None, alertas=None, chave_vence=None,
           historico=None, metas=None, cobertura_ini=None):
    """Devolve (html, nomes_dos_gráficos_omitidos).

    alertas: faixas de destaque no topo (ex.: chave perto de vencer).
    chave_vence: data de vencimento da chave, só informativa, no rodapé.
    historico: todas as atividades guardadas (para os recordes).
    metas: lista de metas do usuário com o progresso (ver metas.progresso).
    cobertura_ini: data (texto ISO) em que começam os dados guardados."""
    hoje = fim
    sem0 = segunda(hoje)
    disponiveis = (fim - ini).days + 1
    opcoes = tuple(n for n in OPCOES if n <= disponiveis) or (PADRAO,)
    padrao = PADRAO if PADRAO in opcoes else opcoes[-1]
    atual = totais_semana(atividades, sem0)
    kpis = (
        f'<div class="kpi"><div class="r">Distância total da semana</div>'
        f'<div class="v">{esc(km(atual["dist_m"]))}</div></div>'
        f'<div class="kpi"><div class="r">Corridas na semana</div>'
        f'<div class="v">{atual["n"]}</div></div>'
        f'<div class="kpi s"><div class="r">Tempo correndo</div>'
        f'<div class="v">{esc(hms(atual["dur_s"]) if atual["n"] else SEM_DADO)}</div></div>'
        f'<div class="kpi s"><div class="r">Pace médio</div>'
        f'<div class="v">{esc(pace(atual["pace"]))}</div></div>')

    omitidos, blocos = [], []
    if metas:
        blocos.append(cartao("Suas metas", "progresso até hoje", card_metas(metas)))
    blocos.append(cartao("Esta semana × semana passada × média",
                         "corridas · números da Garmin",
                         card_comparacao(comparar_semanas(atividades, hoje, ini))))
    blocos.append(cartao("Tempo por esporte — semana atual",
                         f"{intervalo(sem0, sem0 + dt.timedelta(days=6))} · passe o mouse sobre uma fatia",
                         graf_anel(atividades, sem0, sem0 + dt.timedelta(days=6))))

    def por_periodo(fn):
        """Gera o gráfico para cada período; None se não há dado em nenhum."""
        partes = {n: fn(janela(fim, n)) for n in opcoes}
        if all(v is None for v in partes.values()):
            return None
        return "".join(
            f'<div class="per" data-n="{n}">'
            + (v if v is not None else f'<p class="sd">sem dado nos últimos {n} dias.</p>')
            + "</div>" for n, v in partes.items())

    def add(nome, titulo, sub, conteudo):
        if conteudo is None:
            omitidos.append(nome)
        else:
            blocos.append(cartao(titulo, sub, conteudo))

    sub = "passe o mouse sobre um dia · use o seletor de período acima"
    add("Treino por dia", "Treino por dia", sub, por_periodo(lambda j: graf_treino(j, atividades, hoje)))
    add("Sono", "Sono por noite — profundo, leve e REM", sub, por_periodo(lambda j: graf_sono(j, dias, hoje)))
    add("Passos", "Passos por dia", sub + " · traço dourado = meta da Garmin",
        por_periodo(lambda j: graf_passos(j, dias, hoje)))
    add("Body Battery", "Body Battery — do mínimo ao máximo do dia", sub,
        por_periodo(lambda j: graf_bb(j, dias, hoje)))
    add("FC de repouso", "Frequência cardíaca de repouso (bpm)", sub,
        por_periodo(lambda j: graf_linha(j, dias, hoje, "fc_repouso", "bpm", "FC de repouso")))
    add("VFC", "VFC — média da noite (ms)", sub,
        por_periodo(lambda j: graf_linha(j, dias, hoje, "vfc", "ms", "VFC")))
    add("SpO2", "SpO2 média do dia (%)", sub,
        por_periodo(lambda j: graf_linha(j, dias, hoje, "spo2", "%", "SpO2 média")))
    add("Hidratação", "Hidratação por dia", sub + " · traço dourado = meta de hidratação",
        por_periodo(lambda j: graf_hidratacao(j, dias, hoje)))
    add("Peso", "Peso (kg)", sub + " · cada ponto é uma medição, sem ligar dias sem medição",
        por_periodo(lambda j: graf_linha(j, dias, hoje, "peso", "kg", "Peso", casas=1, pad_min=1)))
    add("Distância por semana", "Distância de corrida por semana",
        f"últimas {MAX_SEMANAS} semanas no máximo · passe o mouse sobre uma semana",
        graf_dist_semana(atividades, ini, hoje))
    add("Zonas de FC por semana", "Tempo por zona de frequência cardíaca",
        "por semana · passe o mouse sobre uma semana", graf_zonas_semana(atividades, ini, hoje))

    semanas, linhas_at, datas_at, linhas_d, datas_d = tabelas(dias, atividades, ini, hoje)
    t_sem = tabela("semanas", ["Semana", "Corridas", "Distância", "Tempo", "Pace médio"], semanas)
    t_at = (tabela("atividades", ["Data", "Esporte", "Nome", "Distância", "Duração", "Pace",
                                  "FC média", "Cadência", "Elevação", "VO2máx"],
                   linhas_at, esq=(0, 1, 2), datas=datas_at)
            if linhas_at else '<p class="sd">sem dado: nenhuma atividade no período.</p>')
    recs = recordes(historico if historico is not None else atividades)
    t_mel = (tabela("recordes", ["Recorde", "Valor", "Detalhe", "Dia"], recs, esq=(0, 2))
             if recs else "")
    t_d = (tabela("dados-diarios", ["Dia", "Passos", "Meta passos", "Treino", "Sono", "Profundo",
                                    "Leve", "REM", "FC repouso", "VFC", "FC mín–máx",
                                    "Estresse médio", "Body Battery", "Min. intensidade",
                                    "Calorias", "Respiração", "SpO2", "Andares", "Peso",
                                    "Hidratação", "Meta hidratação"],
                  linhas_d, datas=datas_d)
           if linhas_d else '<p class="sd">sem dado: nenhum dia no período.</p>')
    if not recs:
        omitidos.append("Recordes")

    txt_hist = ("Histórico guardado desde " + dt.date.fromisoformat(cobertura_ini).strftime("%d/%m/%Y")
                + ". Para ampliar: py garmin_painel.py --historico 365") if cobertura_ini \
        else "Histórico guardado neste computador."
    faixas = "".join(f'<div class="faixa" role="alert"><b>Atenção</b><span>{esc(a)}</span></div>'
                     for a in (alertas or []))
    faixas += ('<div class="faixa" id="velho" role="status" hidden><b>Dados antigos</b>'
               '<span></span></div>')
    rodape_chave = (f" A chave da Garmin vence em {chave_vence.strftime('%d/%m/%Y')}."
                    if chave_vence else "")
    aviso_html = ""
    if omitidos or avisos:
        itens = [f"“{n}” omitido: a Garmin não enviou esse dado no período." for n in omitidos] \
            + list(avisos or [])
        aviso_html = '<p class="nota">' + " ".join(esc(i) for i in itens) + "</p>"

    botoes = "".join(f'<button type="button" data-n="{n}" aria-pressed="{"true" if n == padrao else "false"}">{n} dias</button>'
                     for n in opcoes)
    regras = "".join(f'body[data-n="{n}"] .per[data-n="{n}"]{{display:block}}' for n in opcoes)

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel Garmin</title><style>{CSS}{regras}</style></head>
<body data-n="{padrao}" data-hoje="{hoje.isoformat()}" data-gerado="{agora.strftime('%Y-%m-%dT%H:%M:%S')}"><main>
<div class="top"><h1>Painel Garmin</h1>
<p class="sub">Período: {ini.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')} ·
atualizado em {agora.strftime('%d/%m/%Y %H:%M')}</p></div>

{faixas}
<div class="grid">{kpis}</div>
<div class="seletor" role="group" aria-label="Período dos gráficos e das tabelas diárias">
<span>Período:</span>{botoes}</div>
{"".join(blocos)}

<h2 class="t">Semanas — corridas (segunda a domingo)</h2>{t_sem}
<h2 class="t">Atividades</h2>{t_at}
{('<h2 class="t">Recordes pessoais — corridas</h2><p class="sub">' + esc(txt_hist) + '</p>' + t_mel) if t_mel else ""}
<h2 class="t">Dados diários</h2>{t_d}
{aviso_html}
<p class="nota">Todos os números vêm da Garmin Connect Personal API. “sem dado” (ou espaço
vazio nos gráficos) = a Garmin não enviou esse valor; nunca é preenchido com zero. Dias em
que a Garmin envia 0 passos, 0 calorias ou 0 de FC de repouso aparecem como sem dado. O sono
aparece na data em que você acordou. A média semanal do sono usa todas as noites com dado
da semana (segunda a domingo). Pace e porcentagens são contas feitas com a distância e o
tempo enviados pela Garmin; “melhores esforços” são os tempos mais rápidos que a Garmin
registrou para cada distância dentro de uma corrida; os recordes usam todo o histórico guardado. “Descanso” = nenhuma atividade
registrada naquele dia. Clique no título de uma coluna para ordenar.{esc(rodape_chave)}</p>
</main><div id="tip"></div><script>{JS}</script></body></html>""", omitidos

"""Visual do painel: HTML + gráficos em SVG puro (sem bibliotecas externas).

Regras de dados: só usa o que a Garmin enviou. Dia sem dado fica VAZIO no
gráfico (nunca vira zero) e aparece como "sem dado" no balão e nas tabelas.
Ouro/amarelo é reservado para marcar atenção: meta de passos, média semanal
do sono e o dia de hoje. Nenhum esporte usa essa cor.
"""
import datetime as dt
import html
import math

from formatos import (DIAS_SEMANA, ESPORTES, SEM_DADO, cor_esporte, data_br,
                      grupo, hcurto, hm, hms, km, minutos, num, pace,
                      pace_de_velocidade, rotulo_esporte, segunda,
                      totais_semana)

W, PL, PR, PT, PB, N = 1000, 58, 14, 14, 62, 14
OURO = "#FFD23F"
ROXO = "#8B6CF4"
ROXO_CLARO = "#C4B5FD"
SONO = {"prof": ("Profundo", "#6C4BE8"), "leve": ("Leve", "#A592F5"),
        "rem": ("REM", "#E4DBFF")}
SONO_SEM_FASES = "#6F678C"


def esc(x):
    return html.escape(str(x), quote=True)


# --------------------------------------------------------------- geometria --
def janela(fim):
    return [fim - dt.timedelta(days=N - 1 - i) for i in range(N)]


def slot():
    return (W - PL - PR) / N


def cx(i):
    return PL + slot() * (i + 0.5)


def yv(v, lo, hi, h):
    return PT + (h - PT - PB) * (1 - (v - lo) / (hi - lo))


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


def moldura(h, lo, hi, marcas, fmt, dias, hoje, valores):
    """Grade, eixo Y, datas e linha de valores sob cada dia."""
    out = []
    for t in marcas:
        y = yv(t, lo, hi, h)
        out.append(f'<line class="gl" x1="{PL}" x2="{W - PR}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="yl" x="{PL - 8}" y="{y + 4:.1f}" text-anchor="end">{esc(fmt(t))}</text>')
    yb = h - PB
    for i, d in enumerate(dias):
        cl = "xl hoje" if d == hoje else "xl"
        rot = f"{d.day:02d}/{d.month:02d}" if (i == 0 or d.day == 1) else f"{d.day:02d}"
        out.append(f'<text class="{cl}" x="{cx(i):.1f}" y="{yb + 16}" text-anchor="middle">{DIAS_SEMANA[d.weekday()]}</text>')
        out.append(f'<text class="{cl}" x="{cx(i):.1f}" y="{yb + 29}" text-anchor="middle">{rot}</text>')
        if valores[i]:
            out.append(f'<text class="vl" x="{cx(i):.1f}" y="{yb + 47}" text-anchor="middle">{esc(valores[i])}</text>')
    return "".join(out)


def zonas(h, tips):
    """Retângulos invisíveis, um por dia, que mostram o balão ao passar o mouse."""
    s = slot()
    return "".join(
        f'<rect class="hit" x="{PL + s * i:.1f}" y="{PT}" width="{s:.1f}" '
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
    return (f'<div class="anelbox">{anel}<ul class="leg">{"".join(leg)}</ul></div>')


# ------------------------------------------------ gráfico: treino por dia ---
def graf_treino(dias, acts, hoje):
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
    for i, d in enumerate(dias):
        k = d.isoformat()
        segs = [(g_, por[k][g_]) for g_, _, _ in ESPORTES if g_ in por[k] and por[k][g_]["dur"] > 0]
        bw = slot() * 0.56
        y_base = yv(0, lo, hi, h)
        acc = 0.0
        for j, (g_, e) in enumerate(segs):
            usados.add(g_)
            alt = e["dur"] / 60 / (hi - lo) * (h - PT - PB)
            topo = j == len(segs) - 1
            corpo.append(f'<path d="{barra(cx(i) - bw / 2, y_base - acc - alt, bw, alt, topo)}" '
                         f'fill="{cor_esporte(g_)}" stroke="#120d1c" stroke-width="1.5"/>')
            acc += alt
        if k not in com_ativ:
            corpo.append(f'<text class="desc" transform="translate({cx(i) + 4:.1f},{y_base - 8:.1f}) rotate(-90)">descanso</text>')
            tips.append(tip(data_br(k), "descanso"))
            valores.append("")
        else:
            linhas = [f"{rotulo_esporte(g_)}|{minutos(e['dur']) if e['tem'] else SEM_DADO}"
                      + (f" · {km(e['dist'])}" if e["dist"] else "")
                      for g_, e in sorted(por[k].items(), key=lambda kv: [x[0] for x in ESPORTES].index(kv[0]))]
            tips.append(tip(data_br(k), *linhas, f"Total|{minutos(totais[i]) if totais[i] else SEM_DADO}"))
            valores.append(f"{round(totais[i] / 60)} min" if totais[i] else "")
    leg = "".join(chip(cor_esporte(g_), rotulo_esporte(g_)) for g_, _, _ in ESPORTES if g_ in usados)
    base = moldura(h, lo, hi, marcas, lambda t: f"{t:g}", dias, hoje, valores)
    return (f'<div class="legrow">{leg}<span class="mut">minutos de treino por dia</span></div>'
            + svg(h, base + "".join(corpo) + zonas(h, tips), "Tempo de treino por dia, colorido por esporte"))


# ------------------------------------------------------- gráfico: sono ------
def graf_sono(dias, todos, hoje):
    por = {d["data"]: d for d in todos}
    noites = [por.get(d.isoformat(), {}) for d in dias]
    if not any(n.get("sono_s") for n in noites):
        return None
    totais = [n.get("sono_s") for n in noites]
    h = 320
    vmax = max(t for t in totais if t) / 3600
    lo, hi, marcas = escala(0, vmax, 4, mults=(1, 2, 5, 10))
    corpo, tips, valores = [], [], []
    bw = slot() * 0.56
    for i, d in enumerate(dias):
        n, k = noites[i], d.isoformat()
        if not n.get("sono_s"):
            tips.append(tip(data_br(k), "Sono|sem dado"))
            valores.append("")
            continue
        fases = [(c_, n.get(f"sono_{c_}_s")) for c_ in ("prof", "leve", "rem")]
        y_base = yv(0, lo, hi, h)
        acc = 0.0
        presentes = [(c_, v) for c_, v in fases if v]
        if not presentes:
            alt = n["sono_s"] / 3600 / (hi - lo) * (h - PT - PB)
            corpo.append(f'<path d="{barra(cx(i) - bw / 2, y_base - alt, bw, alt)}" fill="{SONO_SEM_FASES}"/>')
        for j, (c_, v) in enumerate(presentes):
            alt = v / 3600 / (hi - lo) * (h - PT - PB)
            corpo.append(f'<path d="{barra(cx(i) - bw / 2, y_base - acc - alt, bw, alt, j == len(presentes) - 1)}" '
                         f'fill="{SONO[c_][1]}" stroke="#120d1c" stroke-width="1.5"/>')
            acc += alt
        linhas = [f"{SONO[c_][0]}|{hm(v) if v else SEM_DADO}" for c_, v in fases]
        tips.append(tip(data_br(k), *linhas, f"Total|{hm(n['sono_s'])}"))
        valores.append(hcurto(n["sono_s"]))
    # média da semana (segunda a domingo), com todas as noites da semana
    semanas, linhas_media = {}, []
    for d in todos:
        if d.get("sono_s"):
            semanas.setdefault(segunda(dt.date.fromisoformat(d["data"])), []).append(d["sono_s"])
    resumo = []
    for ini_s in sorted(semanas):
        idx = [i for i, d in enumerate(dias) if segunda(d) == ini_s]
        if not idx:
            continue
        media = sum(semanas[ini_s]) / len(semanas[ini_s])
        y = yv(media / 3600, lo, hi, h)
        x1, x2 = PL + slot() * idx[0] + 4, PL + slot() * (idx[-1] + 1) - 4
        linhas_media.append(f'<line class="avg" x1="{x1:.1f}" x2="{x2:.1f}" y1="{y:.1f}" y2="{y:.1f}"/>')
        fim_s = ini_s + dt.timedelta(days=6)
        resumo.append(f'<li><i class="trac"></i>Semana {ini_s.day:02d}/{ini_s.month:02d} a '
                      f'{fim_s.day:02d}/{fim_s.month:02d}: <b>{esc(hm(media))}</b> '
                      f'<span class="mut">({len(semanas[ini_s])} noites com dado)</span></li>')
    leg = "".join(chip(c_, n_) for n_, c_ in SONO.values()) + \
        '<span class="chip"><i class="trac"></i>média da semana</span>'
    base = moldura(h, lo, hi, marcas, lambda t: f"{t:g}h", dias, hoje, valores)
    return (f'<div class="legrow">{leg}</div>'
            + svg(h, base + "".join(corpo) + "".join(linhas_media) + zonas(h, tips),
                  "Sono por noite: profundo, leve e REM")
            + f'<ul class="med">{"".join(resumo)}</ul>')


# ------------------------------------------------------ gráfico: passos -----
def graf_passos(dias, todos, hoje):
    por = {d["data"]: d for d in todos}
    reg = [por.get(d.isoformat(), {}) for d in dias]
    if not any(r.get("passos") for r in reg):
        return None
    h = 320
    topo = max([r.get("passos") or 0 for r in reg] + [r.get("meta_passos") or 0 for r in reg])
    lo, hi, marcas = escala(0, topo, 4)
    corpo, tips, valores = [], [], []
    bw = slot() * 0.56
    tem_meta = False
    for i, d in enumerate(dias):
        r, k = reg[i], d.isoformat()
        p, m = r.get("passos"), r.get("meta_passos")
        y0 = yv(0, lo, hi, h)
        if p:
            alt = p / (hi - lo) * (h - PT - PB)
            corpo.append(f'<path d="{barra(cx(i) - bw / 2, y0 - alt, bw, alt)}" fill="{ROXO}"/>')
        if m:
            tem_meta = True
            y = yv(m, lo, hi, h)
            corpo.append(f'<line class="meta" x1="{cx(i) - bw / 2 - 6:.1f}" x2="{cx(i) + bw / 2 + 6:.1f}" y1="{y:.1f}" y2="{y:.1f}"/>')
        linhas = [f"Passos|{num(p) if p else SEM_DADO}", f"Meta da Garmin|{num(m) if m else SEM_DADO}"]
        tips.append(tip(data_br(k), *linhas))
        valores.append(num(p) if p else "")
    leg = chip(ROXO, "passos") + (
        '<span class="chip"><i class="traco"></i>meta da Garmin</span>' if tem_meta else "")
    base = moldura(h, lo, hi, marcas, lambda t: num(t), dias, hoje, valores)
    return f'<div class="legrow">{leg}</div>' + svg(h, base + "".join(corpo) + zonas(h, tips), "Passos por dia e meta")


# ------------------------------------------------- gráfico: body battery ----
def graf_bb(dias, todos, hoje):
    por = {d["data"]: d for d in todos}
    reg = [por.get(d.isoformat(), {}) for d in dias]
    if not any(r.get("bb_min") is not None and r.get("bb_max") is not None for r in reg):
        return None
    h = 300
    lo, hi, marcas = 0, 100, [0, 25, 50, 75, 100]
    corpo, tips, valores = [], [], []
    bw = slot() * 0.44
    for i, d in enumerate(dias):
        r, k = reg[i], d.isoformat()
        a, b = r.get("bb_min"), r.get("bb_max")
        if a is None or b is None:
            tips.append(tip(data_br(k), "Body Battery|sem dado"))
            valores.append("")
            continue
        y1, y2 = yv(b, lo, hi, h), yv(a, lo, hi, h)
        corpo.append(f'<rect x="{cx(i) - bw / 2:.1f}" y="{y1:.1f}" width="{bw:.1f}" '
                     f'height="{max(y2 - y1, 5):.1f}" rx="{min(7, bw / 2):.1f}" fill="url(#gbb)"/>')
        tips.append(tip(data_br(k), f"Máximo|{b}", f"Mínimo|{a}"))
        valores.append(f"{a}–{b}")
    defs = (f'<linearGradient id="gbb" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{ROXO_CLARO}"/><stop offset="1" stop-color="{ROXO}"/></linearGradient>')
    base = moldura(h, lo, hi, marcas, lambda t: f"{t:g}", dias, hoje, valores)
    return svg(h, base + "".join(corpo) + zonas(h, tips), "Body Battery: mínimo e máximo de cada dia", defs)


# ----------------------------------------------- gráficos de linha ---------
def graf_linha(dias, todos, hoje, campo, unidade, nome):
    por = {d["data"]: d for d in todos}
    vals = [por.get(d.isoformat(), {}).get(campo) for d in dias]
    if not any(v is not None for v in vals):
        return None
    h = 280
    presentes = [v for v in vals if v is not None]
    vmin, vmax = min(presentes), max(presentes)
    pad = max((vmax - vmin) * 0.3, 4)
    lo, hi, marcas = escala(vmin - pad, vmax + pad, 4)
    corpo, tips, valores = [], [], []
    pontos = [(cx(i), yv(v, lo, hi, h)) if v is not None else None for i, v in enumerate(vals)]
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
            corpo.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="5" fill="{ROXO_CLARO}" stroke="#120d1c" stroke-width="2"/>')
            tips.append(tip(data_br(k), f"{nome}|{num(vals[i])} {unidade}"))
            valores.append(num(vals[i]))
    base = moldura(h, lo, hi, marcas, lambda t: num(t), dias, hoje, valores)
    return svg(h, base + "".join(corpo) + zonas(h, tips), f"{nome} por dia")


# --------------------------------------------------------------- tabelas ----
def tabela(cabecalho, linhas, esq=(0,)):
    """esq: índices das colunas de texto, alinhadas à esquerda."""
    h = "".join(f'<th class="{"e" if i in esq else ""}">{esc(x)}</th>'
                for i, x in enumerate(cabecalho))

    def cel(i, x):
        t = esc(x)
        cl = ("e " if i in esq else "") + ("sd" if x == SEM_DADO else "")
        return f'<td class="{cl.strip()}">{t}</td>'
    corpo = "".join("<tr>" + "".join(cel(i, x) for i, x in enumerate(l)) + "</tr>"
                    for l in linhas)
    return f'<div class="tw"><table><tr>{h}</tr>{corpo}</table></div>'


def intervalo(ini, fim):
    return f"{ini.day:02d}/{ini.month:02d} a {fim.day:02d}/{fim.month:02d}"


def _min_dia(acts_por_dia, k):
    atv = acts_por_dia.get(k)
    if not atv:
        return "descanso"
    tot = [a["dur_s"] for a in atv if a["dur_s"] is not None]
    return minutos(sum(tot)) if tot else SEM_DADO


def tabelas(dias, atividades, ini, hoje):
    sem0 = segunda(hoje)
    semanas, s = [], sem0
    while s >= segunda(ini):
        t = totais_semana(atividades, s)
        semanas.append([intervalo(t["ini"], t["fim"]), t["n"], km(t["dist_m"]),
                        hms(t["dur_s"]) if t["n"] else SEM_DADO, pace(t["pace"])])
        s -= dt.timedelta(days=7)
    linhas_at = []
    for a in atividades:
        g_ = grupo(a["tipo"])
        com_pace = g_ in ("corrida", "caminhada")
        linhas_at.append([data_br(a["data"]),
                          rotulo_esporte(g_) if a["tipo"] else SEM_DADO,
                          a["nome"] or SEM_DADO, km(a["dist_m"]), hms(a["dur_s"]),
                          pace(pace_de_velocidade(a["vel_ms"])) if com_pace else SEM_DADO])
    por_dia = {}
    for a in atividades:
        if a["data"]:
            por_dia.setdefault(a["data"], []).append(a)
    linhas_d = []
    for d in reversed(dias):
        def par(a, b, suf=""):
            return f"{d[a]}–{d[b]}{suf}" if d.get(a) is not None and d.get(b) is not None else SEM_DADO
        sec = lambda k: hm(d.get(k)) if d.get(k) else SEM_DADO  # noqa: E731
        linhas_d.append([
            data_br(d["data"]), num(d.get("passos")), num(d.get("meta_passos")),
            _min_dia(por_dia, d["data"]),
            hm(d.get("sono_s")) if d.get("sono_s") else SEM_DADO,
            sec("sono_prof_s"), sec("sono_leve_s"), sec("sono_rem_s"),
            f'{d["fc_repouso"]} bpm' if d.get("fc_repouso") else SEM_DADO,
            f'{num(d["vfc"])} ms' if d.get("vfc") else SEM_DADO,
            par("fc_min", "fc_max", " bpm"), num(d.get("estresse")),
            par("bb_min", "bb_max"), num(d.get("intensidade")), num(d.get("calorias")),
            num(d.get("respiracao")), num(d.get("spo2")), num(d.get("andares"))])
    return semanas, linhas_at, linhas_d


# ---------------------------------------------------------------- página ----
CSS = """
:root{--bg:#0b0813;--card:rgba(26,19,42,.78);--bd:rgba(167,139,250,.2);
--tx:#ece8f8;--mut:#a79fc2;--ouro:#FFD23F;--roxo:#8B6CF4;--roxo2:#C4B5FD;
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
.ch{width:100%;height:auto;display:block}
.ch text,.anel text{font-family:var(--mono);fill:var(--mut);font-size:11px}
.ch .xl.hoje{fill:var(--ouro);font-weight:700}.ch .vl{fill:var(--tx);font-weight:700;font-size:11px}
.ch .desc{fill:var(--mut);letter-spacing:.08em}
.anel .rg{font-size:26px;font-weight:700;fill:var(--tx)}.anel .rs{font-size:12px}
.gl{stroke:rgba(167,139,250,.14);stroke-width:1}
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
.tw{overflow-x:auto;background:var(--card);border:1px solid var(--bd);border-radius:18px}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{padding:9px 12px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--bd);
font-family:var(--mono);font-variant-numeric:tabular-nums}
th{color:var(--mut);font-weight:700;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;font-family:"Segoe UI",sans-serif}
th.e,td.e{text-align:left}tr:last-child td{border-bottom:0}
h2.t{margin-top:30px}
.nota{color:var(--mut);font-size:.8rem;margin-top:28px}
#tip{position:fixed;z-index:9;display:none;pointer-events:none;min-width:170px;max-width:290px;
background:#1b1430;border:1px solid var(--roxo);border-radius:12px;padding:10px 12px;
box-shadow:0 10px 30px rgba(0,0,0,.5);font-size:.82rem}
#tip .th{font:900 .8rem var(--titulo);text-transform:uppercase;margin-bottom:5px;color:var(--roxo2)}
#tip .tr{display:flex;justify-content:space-between;gap:14px}
#tip .tv{font-family:var(--mono);font-weight:700;text-align:right;white-space:nowrap}
"""

JS = """
(function(){
var tip=document.getElementById('tip');
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
})();
"""


def pagina(dias, atividades, ini, fim, agora, avisos=None):
    """Devolve (html, nomes_dos_gráficos_omitidos)."""
    hoje = fim
    sem0 = segunda(hoje)
    jan = janela(fim)
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

    sub14 = f"Últimos 14 dias ({intervalo(jan[0], jan[-1])}) · passe o mouse sobre um dia"
    omitidos, blocos = [], []

    blocos.append(cartao(f"Tempo por esporte — semana atual",
                         f"{intervalo(sem0, sem0 + dt.timedelta(days=6))} · passe o mouse sobre uma fatia",
                         graf_anel(atividades, sem0, sem0 + dt.timedelta(days=6))))
    blocos.append(cartao("Treino por dia", sub14, graf_treino(jan, atividades, hoje)))

    def opcional(nome, titulo, sub, conteudo):
        if conteudo is None:
            omitidos.append(nome)
        else:
            blocos.append(cartao(titulo, sub, conteudo))

    opcional("Sono", "Sono por noite — profundo, leve e REM", sub14, graf_sono(jan, dias, hoje))
    opcional("Passos", "Passos por dia", sub14 + " · traço dourado = meta da Garmin", graf_passos(jan, dias, hoje))
    opcional("Body Battery", "Body Battery — do mínimo ao máximo do dia", sub14, graf_bb(jan, dias, hoje))
    opcional("FC de repouso", "Frequência cardíaca de repouso (bpm)", sub14,
             graf_linha(jan, dias, hoje, "fc_repouso", "bpm", "FC de repouso"))
    opcional("VFC", "VFC — média da noite (ms)", sub14,
             graf_linha(jan, dias, hoje, "vfc", "ms", "VFC"))

    semanas, linhas_at, linhas_d = tabelas(dias, atividades, ini, hoje)
    t_sem = tabela(["Semana", "Corridas", "Distância", "Tempo", "Pace médio"], semanas)
    t_at = (tabela(["Data", "Esporte", "Nome", "Distância", "Duração", "Pace"], linhas_at, esq=(0, 1, 2))
            if linhas_at else '<p class="sd">sem dado: nenhuma atividade no período.</p>')
    t_d = (tabela(["Dia", "Passos", "Meta passos", "Treino", "Sono", "Profundo", "Leve", "REM",
                   "FC repouso", "VFC", "FC mín–máx", "Estresse médio", "Body Battery",
                   "Min. intensidade", "Calorias", "Respiração", "SpO2", "Andares"], linhas_d)
           if linhas_d else '<p class="sd">sem dado: nenhum dia no período.</p>')

    aviso_html = ""
    if omitidos or avisos:
        itens = [f"Gráfico “{n}” omitido: a Garmin não enviou esse dado nos últimos 14 dias."
                 for n in omitidos] + list(avisos or [])
        aviso_html = '<p class="nota">' + " ".join(esc(i) for i in itens) + "</p>"

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel Garmin</title><style>{CSS}</style></head><body><main>
<div class="top"><h1>Painel Garmin</h1>
<p class="sub">Período: {ini.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')} ·
atualizado em {agora.strftime('%d/%m/%Y %H:%M')}</p></div>

<div class="grid">{kpis}</div>
{"".join(blocos)}

<h2 class="t">Semanas — corridas (segunda a domingo)</h2>{t_sem}
<h2 class="t">Atividades</h2>{t_at}
<h2 class="t">Dados diários</h2>{t_d}
{aviso_html}
<p class="nota">Todos os números vêm da Garmin Connect Personal API. “sem dado” (ou espaço
vazio nos gráficos) = a Garmin não enviou esse valor; nunca é preenchido com zero. Dias em
que a Garmin envia 0 passos, 0 calorias ou 0 de FC de repouso aparecem como sem dado. O sono
aparece na data em que você acordou. A média semanal do sono usa todas as noites com dado
da semana (segunda a domingo). Pace e porcentagens são contas feitas com a distância e o
tempo enviados pela Garmin. “Descanso” = nenhuma atividade registrada naquele dia.</p>
</main><div id="tip"></div><script>{JS}</script></body></html>""", omitidos

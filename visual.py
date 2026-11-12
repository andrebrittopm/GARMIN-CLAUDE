"""Visual do painel: HTML + gráficos em SVG puro (sem bibliotecas externas).

Regras de dados: só usa o que a Garmin enviou. Dia sem dado fica VAZIO no
gráfico (nunca vira zero) e aparece como "sem dado" no balão e nas tabelas.
Ouro/amarelo é reservado para marcar atenção: meta de passos, média semanal
do sono e o dia de hoje / semana atual. Nenhum esporte usa essa cor.
"""
import contextlib
import datetime as dt
import html
import math

from arte import (arte_topo, arte_topo_real, foto_exemplo, perfil_elevacao_svg,
                  rota_real_svg, rotas_sobrepostas_svg, selo_iniciais)
import rotas as rotas_mod
import plano as plano_mod
from plano import mmss_min
from formatos import (DIAS_SEMANA, ESPORTES, MELHORES, SEM_DADO, comparar_semanas, cor_esporte, data_br,
                      grupo, hcurto, hm, hms, km, minutos, num, pace,
                      pace_de_velocidade, rotulo_esporte, segunda,
                      totais_semana)

W, PL, PR, PT, PB = 1000, 58, 14, 14, 62
LIN_ATUAL = (16, 29, 47)
LARG_CEL, PL_CEL, PB_CEL = 430, 54, 80   # largura/margens (unidades do desenho) da versão para celular
LIN, LIN_CEL = (16, 29, 47), (19, 37, 58)  # posição das linhas de rótulo sob as colunas
OPCOES_CEL = (7, 14)                # períodos oferecidos no celular
GRAFICO_CEL_PX = 700                # abaixo disso o navegador usa a versão para celular


@contextlib.contextmanager
def dimensoes(w, pl, pb=None, lin=None):
    """Desenha os gráficos com outra largura (celular), sem mexer nas funções."""
    global W, PL, PB, LIN_ATUAL
    ant = (W, PL, PB, LIN_ATUAL)
    W, PL = w, pl
    if pb is not None:
        PB = pb
    if lin is not None:
        LIN_ATUAL = lin
    try:
        yield
    finally:
        W, PL, PB, LIN_ATUAL = ant


def _curto(p, m):
    """Número grande em coluna estreita: 11.816 vira 11,8k (o balão mostra o valor exato)."""
    return f"{p / 1000:.1f}k".replace(".", ",") if slot(m) < 58 and p >= 10000 else num(p)


def mostra_valores(m):
    """A linha de números sob as colunas só cabe quando cada coluna é larga."""
    return slot(m) >= 48
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
    """(linha1, linha2, destaque) por dia; None onde o rótulo é omitido.
    O nível de detalhe depende da largura de cada coluna (computador x celular)."""
    n, out, primeiro = len(dias), [], True
    s = slot(n)
    for i, d in enumerate(dias):
        resto = n - 1 - i
        if s >= 48:
            pular = n > 16 and resto % 2 != 0     # computador, período longo: um sim, um não
        elif s >= 22:
            pular = False                          # celular, 14 dias
        else:
            pular = resto % 3 != 0                 # coluna muito estreita: um a cada três
        if pular:
            out.append(None)
            continue
        if s >= 48:
            rot = f"{d.day:02d}/{d.month:02d}" if (d.day == 1 or primeiro) else f"{d.day:02d}"
            linha1 = DIAS_SEMANA[d.weekday()]
        else:                                   # coluna estreita: inicial do dia + número
            rot = f"{d.day:02d}"
            linha1 = DIAS_SEMANA[d.weekday()][0]
        primeiro = False
        out.append((linha1, rot, d == hoje))
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
        out.append(f'<text class="{cl}" x="{cx(i, m):.1f}" y="{yb + LIN_ATUAL[0]}" text-anchor="middle">{esc(r[0])}</text>')
        out.append(f'<text class="{cl}" x="{cx(i, m):.1f}" y="{yb + LIN_ATUAL[1]}" text-anchor="middle">{esc(r[1])}</text>')
        if valores[i]:
            out.append(f'<text class="vl" x="{cx(i, m):.1f}" y="{yb + LIN_ATUAL[2]}" text-anchor="middle">{esc(valores[i])}</text>')
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
            valores.append((f"{round(totais[i] / 60)}" + (" min" if slot(m) >= 66 else "")) if totais[i] else "")
    leg = "".join(chip(cor_esporte(g_), rotulo_esporte(g_)) for g_, _, _ in ESPORTES if g_ in usados)
    if not mostra_valores(m):
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
    if not mostra_valores(m):
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
        valores.append(_curto(p, m) if p and mostra_valores(m) else "")
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
        valores.append(f"{a}–{b}" if mostra_valores(m) else "")
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
            valores.append(num(vals[i], casas) if mostra_valores(m) else "")
    base = moldura(h, lo, hi, marcas, lambda t: num(t, casas), rotulos_dias(dias, hoje), valores)
    return svg(h, base + "".join(corpo) + zonas(h, tips), f"{nome} por dia")


# ------------------------------------------- gráficos por semana (novos) ---
def semanas_lista(ini, hoje):
    s, out = segunda(hoje), []
    maximo = MAX_SEMANAS if W >= 800 else 8
    while s >= segunda(ini) and len(out) < maximo:
        out.append(s)
        s -= dt.timedelta(days=7)
    return list(reversed(out))


def _rot_sem(semanas, hoje):
    folga = slot(len(semanas)) >= 42
    n = len(semanas)
    return [("sem", f"{s.day:02d}/{s.month:02d}", s == segunda(hoje)) if (folga or (n - 1 - i) % 2 == 0) else None
            for i, s in enumerate(semanas)]


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
            valores.append(f"{num(t['dist_m'] / 1000, 1)} km" if slot(m) >= 56 else "")
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
        valores.append(f"{round(sum(z) / 60)} min" if slot(m) >= 56 else "")
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


def tabela(nome, cabecalho, linhas, esq=(0,), datas=None, classes=None):
    """Tabela ordenável (clique no título) com botão de exportar CSV.
    Cada célula pode ser texto ou (texto, valor_para_ordenar)."""
    h = "".join(f'<th class="ord{" e" if i in esq else ""}" tabindex="0" role="button" '
                f'aria-label="Ordenar por {esc(x)}">{esc(x)}</th>'
                for i, x in enumerate(cabecalho))
    corpo = []
    for n, l in enumerate(linhas):
        d = f' data-d="{datas[n]}"' if datas and datas[n] else ""
        if classes and classes[n]:
            d += f' class="{classes[n][0]}" title="Ritmo {esc(classes[n][1])} (comparado ao seu equivalente em 10 km)"'
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


def _equiv_cel(a):
    e = plano_mod.equivalente_de(a)
    if e is not None:
        return _v(hms(e), e)
    if grupo(a["tipo"]) == "corrida" and a.get("dist_m") and a["dist_m"] < plano_mod.MIN_EQUIV_M:
        return ("abaixo de 5 km", "")
    return (SEM_DADO if grupo(a["tipo"]) == "corrida" else "", "")


def tabelas(dias, atividades, ini, hoje, ref_pace=None):
    sem0 = segunda(hoje)
    semanas, s = [], sem0
    while s >= segunda(ini):
        t = totais_semana(atividades, s)
        semanas.append([(intervalo(t["ini"], t["fim"]), s.isoformat()), t["n"],
                        _v(km(t["dist_m"]), t["dist_m"]),
                        _v(hms(t["dur_s"]) if t["n"] else SEM_DADO, t["dur_s"]),
                        _v(pace(t["pace"]), t["pace"])])
        s -= dt.timedelta(days=7)
    linhas_at, datas_at, classes_at = [], [], []
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
            _v(num(a["vo2"]) if a.get("vo2") else SEM_DADO, a.get("vo2")),
            _equiv_cel(a)])
        datas_at.append(a["data"])
        classes_at.append(plano_mod.zona_ritmo(pc, ref_pace) if grupo(a["tipo"]) == "corrida" else None)
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
    return semanas, linhas_at, datas_at, linhas_d, datas_d, classes_at


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


# ---------------------------------------------------- visual de corredor ----
def _dist_txt(d_km):
    return f"{num(d_km, 0 if float(d_km).is_integer() else 1)} km"


def _logo(p):
    if p.get("logo_uri"):
        return f'<img class="logo-img" src="{p["logo_uri"]}" alt="Logo {esc(p["nome"])}">'
    return selo_iniciais(p["nome"])


def _data_curta(d):
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return f"{d.day:02d} {meses[d.month - 1]} {d.year}"


def card_prova_proxima(p):
    dist = _dist_txt(p["dist_km"]).upper() if p.get("dist_km") else ""
    tag = f"PRÓXIMA · {esc(dist)}" if dist else "PRÓXIMA"
    n = p["dias"]
    return (f'<article class="bib prox"><div class="furos"></div>{_logo(p)}'
            f'<div class="corpo"><span class="tag">{tag}</span><h3>{esc(p["nome"])}</h3>'
            f'<p class="mut">{_data_curta(p["data"])}</p></div>'
            f'<div class="conta"><span class="n">{"hoje" if n == 0 else n}</span>'
            f'<span>{"" if n == 0 else ("dia" if n == 1 else "dias")}</span></div></article>')


def card_prova_feita(p, minis=None):
    a = p.get("atv")
    if p.get("dist_km"):
        dist = _dist_txt(p["dist_km"]).upper()
    else:
        dist = km(a["dist_m"]).upper() if a and a.get("dist_m") else ""
    rotulo = "COMPETIÇÃO" if p.get("origem") == "garmin" else "CORRIDA"
    tag = f"{rotulo} · {esc(dist)}" if dist else rotulo
    if a:
        tempo, ritmo = hms(a["dur_s"]), pace(pace_de_velocidade(a["vel_ms"]))
        real = f'<div><dt>Garmin</dt><dd>{esc(km(a["dist_m"]))}</dd></div>'
    else:
        tempo = ritmo = SEM_DADO
        real = ""
    aid = str(a["id"]) if a and a.get("id") is not None else None
    mini = (f'<button type="button" class="mini" data-det="{aid}" aria-label="Ver o percurso desta prova">{minis[aid]}</button>'
            if aid and minis and aid in minis else "")
    return (f'<article class="bib feita"><div class="furos"></div>{_logo(p)}'
            f'<div class="corpo"><span class="tag ok">{tag}</span><h3>{esc(p["nome"])}</h3>'
            f'<p>{_data_curta(p["data"])}</p></div>'
            f'<dl class="num"><div><dt>Tempo</dt><dd>{esc(tempo)}</dd></div>'
            f'<div><dt>Pace</dt><dd>{esc(ritmo)}</dd></div>{real}</dl>{mini}</article>')


def hero_html(co, agora, rotas_xy=None):
    per = co["perfil"]
    foto = (f'<img src="{per["foto_uri"]}" alt="Foto de {esc(per["nome"])}">'
            if per["foto_uri"] else foto_exemplo(False))
    p = co["periodo"]
    sufixo = "no ano" if p["do_ano"] else f"desde {p['desde'].day:02d}/{p['desde'].month:02d}"
    stats = [("Distância " + sufixo, km(p["dist_m"]) if p["n"] else SEM_DADO, ""),
             ("Corridas " + sufixo, str(p["n"]), ""),
             ("Provas corridas", str(len(co["feitas"])), "")]
    if co["proximas"]:
        n = min(x["dias"] for x in co["proximas"])
        stats.append(("Próxima prova em", "hoje" if n == 0 else f"{n} {'dia' if n == 1 else 'dias'}", "ouro"))
    hs = "".join(f'<div class="hs {cl}"><div class="r">{esc(r)}</div><div class="v">{esc(v)}</div></div>'
                 for r, v, cl in stats)
    frase = f'<p class="sub" style="margin:0">{esc(per["frase"])}</p>' if per["frase"] else ""
    arte = arte_topo_real(rotas_xy) if rotas_xy else arte_topo()
    return (f'<header class="hero">{arte}<div class="hero-in">'
            f'<div class="avatar">{foto}</div>'
            f'<div><p class="eyebrow">PAINEL DO CORREDOR</p><h1>{esc(per["nome"])}</h1>{frase}'
            f'<p class="sub" style="margin:6px 0 0">Período: {{ini}} a {{fim}} · atualizado em {agora.strftime("%d/%m/%Y %H:%M")}</p></div>'
            f'<div class="hero-stats">{hs}</div></div></header>')


def _st(rotulo, valor):
    return (f'<div class="det-st"><div class="r">{esc(rotulo)}</div>'
            f'<div class="v{" sd" if valor == SEM_DADO else ""}">{esc(valor)}</div></div>')


def detalhe_html(it, priv):
    """Conteúdo da janela de detalhe de UMA corrida (números da Garmin)."""
    alt = it.get("alt") or []
    faixa = (f"{round(min(p[1] for p in alt))}–{round(max(p[1] for p in alt))} m" if alt else SEM_DADO)
    stats = [("Distância", km(it["dist_m"])), ("Tempo", hms(it["dur_s"])),
             ("Pace", pace(pace_de_velocidade(it["vel_ms"]))),
             ("FC média", f'{num(it["fc_media"])} bpm' if it.get("fc_media") else SEM_DADO),
             ("Cadência", f'{num(it["cad"])} ppm' if it.get("cad") else SEM_DADO),
             ("Ganho de elevação", f'{num(it["elev_m"])} m' if it.get("elev_m") is not None else SEM_DADO),
             ("Altitude mín–máx", faixa),
             ("VO2máx", num(it["vo2"]) if it.get("vo2") else SEM_DADO)]
    mapa = rota_real_svg(rotas_mod.projetar(it["pts"]), "d" + str(it["id"]), 420, 300,
                         rotulo="Rota de " + data_br(it["data"]))
    perfil = perfil_elevacao_svg(alt)
    perfil_cel = perfil_elevacao_svg(alt, LARG_CEL, 230)
    perfil_html = (f'<h3 class="det-h">Perfil de elevação</h3><div class="dv desk">{perfil}</div>'
                   f'<div class="dv mob">{perfil_cel}</div>' if perfil else
                   '<p class="sd">Perfil de elevação: sem dado (será baixado nas próximas atualizações).</p>')
    nota = (f"o começo e o fim ficam ocultos (primeiros e últimos {priv} m)" if priv
            else "atenção: sem corte de privacidade")
    return (f'<div class="det-grid">{"".join(_st(r, v_) for r, v_ in stats)}</div>'
            f'<div class="det-mapa">{mapa}<p class="sub">{esc(nota)}</p></div>{perfil_html}')


def secao_rotas(info, ids_extra=()):
    """Galeria das últimas rotas + mapa de todas sobrepostas + janelas de detalhe.
    Devolve (html, rotas_xy_do_topo, templates_html, minis{id: svg})."""
    itens = info["itens"] if info else []
    if not itens:
        return "", [], "", {}
    priv = info["privacidade_m"]
    nota_priv = (f"o começo e o fim de cada rota ficam ocultos (primeiros e últimos {priv} m)" if priv
                 else "atenção: sem corte de privacidade, o início e o fim aparecem")
    com_detalhe = {it["id"] for it in itens[-60:]} | {i for i in ids_extra if any(it["id"] == i for it in itens)}
    cards = []
    for it in reversed(itens[-12:]):
        pc = pace(pace_de_velocidade(it["vel_ms"]))
        t = tip(data_br(it["data"]), f"Distância|{km(it['dist_m'])}", f"Tempo|{hms(it['dur_s'])}", f"Pace|{pc}")
        cards.append(
            f'<div class="rota" data-tip="{esc(t)}" data-det="{it["id"]}" tabindex="0" role="button" '
            f'aria-label="Ver detalhes da corrida de {esc(data_br(it["data"]))}">'
            f'{rota_real_svg(rotas_mod.projetar(it["pts"]), "r" + str(it["id"]), rotulo="Rota de " + data_br(it["data"]))}'
            f'<div class="cap"><span>{esc(data_br(it["data"]))}</span><b>{esc(km(it["dist_m"]))}</b>'
            f'<span class="mut">{esc(pc)}</span></div></div>')
    idx, fora = rotas_mod.area_principal([it["pts"] for it in itens])
    lat0 = sum(rotas_mod.centro(itens[i]["pts"])[0] for i in idx) / len(idx)
    xy = [rotas_mod.projetar(itens[i]["pts"], lat0) for i in sorted(idx)]
    nota_fora = (f" · {fora} corrida{'s' if fora != 1 else ''} em outra região não entra neste mapa"
                 if fora else "")
    sec = (cartao("Meus percursos",
                  f"as {min(len(itens), 12)} corridas mais recentes com trilha · clique numa rota para ver o detalhe · {nota_priv}",
                  f'<div class="galeria">{"".join(cards)}</div>')
           + cartao("Todas as minhas rotas",
                    f"{len(idx)} corridas sobrepostas, na mesma escala: onde mais passei fica mais intenso; "
                    f"as mais recentes são mais claras{nota_fora} · sem mapa de fundo, nada é enviado a ninguém",
                    f'<div class="mapa">{rotas_sobrepostas_svg(xy)}</div>'))
    templates = "".join(
        f'<template id="det-{it["id"]}" data-titulo="{esc(data_br(it["data"]) + " — " + (it.get("nome") or "Corrida"))}">'
        f'{detalhe_html(it, priv)}</template>' for it in itens if it["id"] in com_detalhe)
    minis = {it["id"]: rota_real_svg(rotas_mod.projetar(it["pts"]), "m" + str(it["id"]), 300, 90,
                                     rotulo="Rota da prova")
             for it in itens if it["id"] in ids_extra}
    hero_xy = [rotas_mod.projetar(itens[i]["pts"]) for i in range(len(itens) - 1, max(len(itens) - 10, -1), -1)]
    return sec, hero_xy, templates, minis


def provas_html(co, minis=None):
    out = ""
    if co["proximas"]:
        out += ('<h2 class="t">Próximas provas</h2><div class="provas">'
                + "".join(card_prova_proxima(p) for p in co["proximas"]) + "</div>")
    if co["feitas"]:
        out += ('<h2 class="t">Provas que já corri</h2><div class="provas">'
                + "".join(card_prova_feita(p, minis) for p in co["feitas"]) + "</div>"
                '<p class="sub" style="margin-top:8px">Tempo, pace e distância vêm da atividade da Garmin '
                'no dia da prova; podem diferir do tempo oficial da organização.</p>')
    return out


MEDALHAS = ["Mais rápido: 1 km", "Mais rápido: 5 km", "Mais rápido: 10 km",
            "Mais rápido: Meia maratona", "Corrida mais longa"]


def medalhas_html(recs):
    por = {r[0]: r for r in recs}
    itens = []
    for nome in MEDALHAS:
        if nome in por:
            r = por[nome]
            txt = r[1][0] if isinstance(r[1], tuple) else r[1]
            dia = r[3][0] if isinstance(r[3], tuple) else r[3]
            if " " in txt:
                n_, u_ = txt.split(" ", 1)
                val = f"{esc(n_)}<small>{esc(u_)}</small>"
            else:
                val = esc(txt)
            itens.append(f'<div class="medalha"><div class="anel"><span>{val}</span></div>'
                         f'<div class="t1">{esc(nome.replace("Mais rápido: ", ""))}</div>'
                         f'<div class="t2">{esc(dia)}</div></div>')
    return f'<div class="medalhas">{"".join(itens)}</div>' if itens else ""


# ------------------------------------------------ plano / meta da prova ----
FASE_CORES = ["#56B4E9", "#E69F00", "#CC79A7", "#009E73", "#F0E442", "#D55E00", "#999999"]


def card_rumo(c):
    """Contagem regressiva e barra do equivalente em 10 km até a meta (só números da Garmin + Riegel)."""
    if c["dias"] > 0:
        dias = f'{c["dias"]}<small> dias</small>'
        nota = f'até a largada em {data_br(c["data"].isoformat())}'
    elif c["dias"] == 0:
        dias, nota = "Hoje", "é o dia da prova"
    else:
        dias, nota = "Prova realizada", f'em {data_br(c["data"].isoformat())}'
    meta = mmss_min(c["meta_s"] / 60) if c["meta_s"] else None
    atual = c["atual"]
    barra = ""
    if c["frac"] is not None:
        pc = round(c["frac"] * 100)
        barra = (f'<div class="trilho" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pc}" '
                 f'aria-label="Caminho até a meta"><i class="enche" style="width:{pc}%"></i></div>'
                 f'<div class="txt rumo-txt"><span class="vv">início do plano {esc(hms(c["inicio"][0]))}</span>'
                 f'<span class="vv pct">{pc}%</span><span class="vv">meta {esc(meta)}</span></div>')
    elif c["meta_s"]:
        falta = ("sem corrida de 5 km ou mais nos últimos 60 dias" if not atual else
                 "sem ponto de partida (nenhuma corrida de 5 km ou mais em volta do início do plano)")
        barra = f'<p class="sd">Barra até a meta: {esc(falta)}.</p>'
    ref = (f'<div class="rumo-eq"><span class="r">Melhor equivalente em 10 km (últimos 60 dias)</span>'
           f'<span class="v">{esc(hms(atual[0]))}</span>'
           f'<span class="mut">corrida de {data_br(atual[1])}, {esc(km(atual[2]["dist_m"]))} em {esc(hms(atual[2]["dur_s"]))}</span></div>'
           if atual else '<div class="rumo-eq"><span class="r">Melhor equivalente em 10 km</span>'
                         f'<span class="v sd">{SEM_DADO}</span><span class="mut">precisa de uma corrida de 5 km ou mais nos últimos 60 dias</span></div>')
    corpo = (f'<div class="rumo"><div class="rumo-dias"><span class="r">{esc(c["nome"])}</span>'
             f'<span class="v">{dias}</span><span class="mut">{esc(nota)}</span></div>{ref}</div>{barra}'
             '<p class="sub">Equivalente em 10 km = fórmula de Riegel, tempo × (10 ÷ distância)^1,06, '
             'aplicada às corridas de 5 km ou mais (é uma estimativa, não um tempo medido). '
             'A meta é sua, do arquivo plano.json.</p>')
    return cartao("Rumo à prova", f'{c["dist_km"]:g} km · meta e contagem', corpo)


def card_ciclos(lista, hoje):
    fases = []
    for c in lista:
        if c["fase"] and c["fase"] not in fases:
            fases.append(c["fase"])
    cor = {f: FASE_CORES[i % len(FASE_CORES)] for i, f in enumerate(fases)}
    mx = max((c["km"] for c in lista if c["km"]), default=0) or 1
    cel = []
    for c in lista:
        h = 0 if not c["km"] else max(6, round(c["km"] / mx * 100))
        km_txt = SEM_DADO if c["km"] is None else km(c["km"] * 1000)
        t = [f'Ciclo {c["ciclo"]} · {c["fase"] or "sem fase"}',
             f'Período|{intervalo(c["inicio"], c["fim"])}', f'Distância|{km_txt}']
        if c["teste"]:
            t.append(f'Teste|{c["teste"].strftime("%d/%m")}')
        sit = c["situacao"]
        cel.append(
            f'<div class="ci {sit}" style="--c:{cor.get(c["fase"], "#999")}" data-tip="{esc(chr(10).join(t))}" '
            f'tabindex="0" aria-label="{esc(" ".join(t).replace("|", " "))}">'
            f'<div class="ci-b"><i style="height:{h}%"></i></div>'
            f'<span class="ci-n">{c["ciclo"]}</span>'
            f'<span class="ci-k">{esc(num(c["km"], 0)) if c["km"] else ("0" if c["km"] == 0 else "")}</span>'
            + ('<span class="ci-t" title="Teste">★</span>' if c["teste"] else "") + "</div>")
    leg = "".join(f'<span class="chip"><i class="quad" style="--c:{cor[f]}"></i>{esc(f)}</span>' for f in fases)
    ok = [c for c in lista if c["km"] is not None]
    resumo = ""
    if ok:
        resumo = (f'<p class="sub">{len(ok)} de {len(lista)} ciclos já começaram · maior ciclo: '
                  f'{esc(km(max(c["km"] for c in ok) * 1000))}. ★ = data de teste. '
                  'A altura de cada coluna é a distância de corrida do ciclo (Garmin); ciclos futuros ficam vazios.</p>')
    return cartao("Trilha dos ciclos", "um ciclo por coluna · passe o mouse (ou toque) para ver o período",
                  f'<div class="legrow">{leg}</div><div class="ciclos">{"".join(cel)}</div>{resumo}')


def card_selos(lista):
    if not lista:
        return ""
    feitos = sum(1 for s in lista if s["feito"])
    itens = []
    for s in lista:
        pc = round(s["pct"] * 100)
        rod = (f'conquistado em {data_br(s["data"])}' if s["feito"] and s["data"] else
               "conquistado" if s["feito"] else (s["falta"] or f"{pc}%"))
        itens.append(
            f'<div class="selo{" feito" if s["feito"] else ""}"><div class="selo-t"><b>{esc(s["nome"])}</b>'
            f'<span class="mut">{esc(s["desc"])}</span></div>'
            f'<div class="trilho" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pc}" '
            f'aria-label="{esc(s["nome"])}"><i class="enche" style="width:{pc}%"></i></div>'
            f'<div class="selo-r">{esc(rod)}</div></div>')
    return cartao("Conquistas", f"{feitos} de {len(lista)} selos conquistados",
                  '<div class="selos">' + "".join(itens) + '</div>'
                  '<p class="sub">Calculado com as corridas guardadas da Garmin. “No total” soma só o histórico guardado neste computador.</p>')


def card_plano_prova(pl):
    """Passagens km a km para 5, 7, 10, 21 e 42 km (estimativas)."""
    if not pl["base"]:
        return cartao("Plano de prova — ritmo de cada km", "estimativas por distância",
                      f'<p class="sd">{SEM_DADO}: o plano precisa de uma corrida de 5 km ou mais nos últimos 60 dias.</p>')
    dist_btn, blocos = [], []
    for b in pl["blocos"]:
        ativo = b["dist"] == 10
        dist_btn.append(f'<button type="button" class="pl-b" data-d="{b["dist"]}" aria-pressed="{"true" if ativo else "false"}">{b["dist"]} km</button>')
        opt_btn, tabs = [], []
        for i, (nome, t, linhas) in enumerate(b["opcoes"]):
            on = i == 0
            opt_btn.append(f'<button type="button" class="pl-o" data-o="{i}" aria-pressed="{"true" if on else "false"}">{esc(nome)} · {esc(hms(t))}</button>')
            media = t / b["dist_km"]
            res = (f'<div class="pl-sum"><span><b>{esc(hms(t))}</b> tempo total</span>'
                   f'<span><b>{esc(pace(media))}</b> ritmo médio</span>'
                   + ('<span class="mut">ajustado ao relevo da prova</span>' if b["alt"] else "") + "</div>")
            corpo = []
            for r in linhas:
                terreno = ("" if r["dz"] is None else ("plano" if abs(r["dz"]) < 4 else
                           ("▲ " if r["dz"] > 0 else "▼ ") + f'{num(abs(r["dz"]))} m'))
                lab = f'{r["km"]}' if r["dist"] == 1.0 else f'{r["km"] - 1 + r["dist"]:.3f}'.rstrip("0").replace(".", ",")
                ritmo = pace(r["t"] / r["dist"])
                corpo.append(f'<tr><td class="e">{esc(lab)}</td>'
                             + (f'<td class="e">{esc(terreno)}</td>' if b["alt"] else "")
                             + f'<td>{esc(ritmo)}</td><td>{esc(hms(r["acum"]))}</td></tr>')
            cab = ('<th class="e">km</th>' + ('<th class="e">terreno</th>' if b["alt"] else "")
                   + '<th>ritmo</th><th>passagem</th>')
            tabs.append(f'<div class="pl-t{" on" if on else ""}" data-o="{i}">{res}<div class="tw pl-tw"><table class="pl-tab">'
                        f'<thead><tr>{cab}</tr></thead><tbody>{"".join(corpo)}</tbody></table></div></div>')
        aviso = ('<p class="sub">Para 21 e 42 km a fórmula de Riegel costuma dar tempos mais rápidos do que se consegue sem treino '
                 'específico para a distância; trate como referência de cálculo.</p>' if b["dist"] >= 21 else "")
        blocos.append(f'<div class="pl-d{" on" if ativo else ""}" data-d="{b["dist"]}"><div class="legrow">{"".join(opt_btn)}</div>'
                      f'{"".join(tabs)}{aviso}</div>')
    base = pl["base"]
    nota = (f'<p class="sub">Previsão de hoje = Riegel a partir do melhor equivalente em 10 km ({esc(hms(base[0]))}, '
            f'corrida de {data_br(base[1])}). Ritmo uniforme; só a prova com perfil de altitude no plano.json é ajustada ao relevo '
            '(custo de Minetti, 2002). São estimativas de cálculo, não promessa nem orientação de treino.</p>')
    return cartao("Plano de prova — ritmo de cada km", "escolha a distância · passe e compare as opções",
                  f'<div class="legrow pl-dist">{"".join(dist_btn)}</div>{"".join(blocos)}{nota}')


def card_calendario(cal, hoje, dias=14):
    """Próximos dias do calendário do intervals.icu: o que está marcado, sem comentário."""
    eventos, buscado = cal
    por_dia = {}
    for e in eventos:
        por_dia.setdefault(e["data"], []).append(e)
    try:
        q = dt.datetime.fromisoformat(buscado)
        quando = f"atualizado em {q.strftime('%d/%m %H:%M')}"
        velho = (dt.datetime.now() - q).total_seconds() > 48 * 3600
    except (TypeError, ValueError):
        quando, velho = "data da busca desconhecida", False
    linhas = []
    for i in range(dias):
        d = hoje + dt.timedelta(days=i)
        evs = por_dia.get(d.isoformat(), [])
        itens = []
        for e in evs:
            det = []
            if e.get("dur_s"):
                det.append(minutos(e["dur_s"]))
            if e.get("dist_m"):
                det.append(km(e["dist_m"]))
            itens.append(f'<li><span class="cal-c">{esc(e["categoria"])}</span><b>{esc(e["nome"])}</b>'
                         + (f'<span class="mut">{esc(" · ".join(det))}</span>' if det else "") + "</li>")
        corpo = f'<ul class="cal-i">{"".join(itens)}</ul>' if itens else '<span class="mut">nada marcado</span>'
        linhas.append(f'<div class="cal-l{" hoje" if i == 0 else ""}"><div class="cal-d">{esc(data_br(d.isoformat()))}'
                      f'{"<small>hoje</small>" if i == 0 else ""}</div>{corpo}</div>')
    aviso = ('<p class="nota" style="margin:6px 0 0">Estes dados têm mais de 2 dias; a última busca pode ter falhado.</p>'
             if velho else "")
    return cartao("Próximos dias", f"calendário do intervals.icu · {quando}",
                  f'<div class="cal">{"".join(linhas)}</div>{aviso}'
                  '<p class="sub">Só o que está marcado no seu calendário do intervals.icu (leitura; o painel nunca altera nada lá).</p>')


PLANO_CSS = """
.rumo{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px 28px;margin-bottom:10px}
.rumo .r{display:block;color:var(--mut);font-size:.74rem;text-transform:uppercase;letter-spacing:.07em}
.rumo .v{display:block;font:700 2.1rem/1.15 var(--mono);color:var(--roxo2)}
.rumo .v small{font-size:1rem;color:var(--mut)}
.cal-l{display:grid;grid-template-columns:120px 1fr;gap:4px 14px;padding:8px 0;border-bottom:1px solid var(--bd)}
.cal-l:last-child{border-bottom:0}.cal-d{font:700 .85rem var(--mono)}.cal-d small{display:block;color:var(--ouro);font-weight:400}
.cal-l.hoje{background:rgba(139,92,246,.08);border-radius:10px;padding-left:8px}
.cal-i{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:3px}
.cal-i li{display:flex;flex-wrap:wrap;gap:2px 10px;align-items:baseline}
.cal-c{font:700 .68rem var(--mono);color:var(--roxo2);text-transform:uppercase;border:1px solid var(--bd);border-radius:999px;padding:1px 8px}
@media(max-width:560px){.cal-l{grid-template-columns:1fr}}
.rumo-txt{display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px 16px;font-size:.82rem}
.ciclos{display:grid;grid-template-columns:repeat(auto-fill,minmax(46px,1fr));gap:8px;margin-top:6px}
.ci{position:relative;display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 2px 5px;border-radius:10px;
border:1px solid var(--bd);background:rgba(139,92,246,.06);min-height:96px}
.ci-b{display:flex;align-items:flex-end;width:20px;height:46px;border-bottom:2px solid var(--c)}
.ci-b i{display:block;width:100%;background:var(--c);border-radius:3px 3px 0 0}
.ci.futuro{opacity:.55}.ci.atual{border-color:var(--ouro);box-shadow:0 0 0 1px var(--ouro)}
.ci-n{font:700 .72rem var(--mono);color:var(--tx)}.ci-k{font:700 .66rem var(--mono);color:var(--mut);min-height:1em}
.ci-t{position:absolute;top:1px;right:4px;font-size:.7rem;color:var(--ouro)}
.selos{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.selo{border:1px solid var(--bd);border-radius:14px;padding:11px 13px;background:rgba(139,92,246,.05)}
.selo.feito{border-color:var(--ouro)}.selo-t b{display:block;font-size:.9rem}.selo-t .mut{font-size:.74rem;display:block;min-height:2.1em}
.selo-r{font:700 .74rem var(--mono);color:var(--mut)}.selo.feito .selo-r{color:var(--ouro)}
.pl-d,.pl-t{display:none}.pl-d.on,.pl-t.on{display:block}
.pl-b,.pl-o{font:700 .8rem var(--mono);color:var(--tx);background:rgba(139,92,246,.12);border:1px solid var(--bd);
border-radius:999px;padding:6px 14px;cursor:pointer}
.pl-b[aria-pressed=true],.pl-o[aria-pressed=true]{background:var(--roxo);border-color:var(--roxo2)}
.pl-dist{margin-bottom:10px}.pl-sum{display:flex;flex-wrap:wrap;gap:6px 22px;margin:8px 0;font-size:.88rem}
.pl-sum b{font-family:var(--mono)}.pl-tw{max-height:460px;overflow:auto}
tr.z1 td:first-child{box-shadow:inset 4px 0 0 #009E73}tr.z2 td:first-child{box-shadow:inset 4px 0 0 #F0E442}
tr.z3 td:first-child{box-shadow:inset 4px 0 0 #E69F00}tr.z4 td:first-child{box-shadow:inset 4px 0 0 #D55E00}
i.z1{background:#009E73}i.z2{background:#F0E442}i.z3{background:#E69F00}i.z4{background:#D55E00}
@media(max-width:560px){.ciclos{grid-template-columns:repeat(auto-fill,minmax(40px,1fr))}.rumo .v{font-size:1.7rem}}
"""

PLANO_JS = """
(function(){
function marca(grupo,sel,alvo){grupo.forEach(function(b){b.setAttribute('aria-pressed',b===alvo?'true':'false');});}
document.querySelectorAll('.pl-b').forEach(function(b){b.addEventListener('click',function(){
  var d=b.getAttribute('data-d');marca(document.querySelectorAll('.pl-b'),'',b);
  document.querySelectorAll('.pl-d').forEach(function(x){x.classList.toggle('on',x.getAttribute('data-d')===d);});});});
document.querySelectorAll('.pl-d').forEach(function(w){var bs=w.querySelectorAll('.pl-o');
  bs.forEach(function(b){b.addEventListener('click',function(){var o=b.getAttribute('data-o');marca(bs,'',b);
    w.querySelectorAll('.pl-t').forEach(function(t){t.classList.toggle('on',t.getAttribute('data-o')===o);});});});});
})();
"""


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
.seletor button,.csv,.btn-editar{font:700 .8rem var(--mono);color:var(--tx);background:rgba(139,92,246,.12);
border:1px solid var(--bd);border-radius:999px;padding:6px 14px;cursor:pointer}
.seletor button:hover,.csv:hover{border-color:var(--roxo2)}
.seletor button[data-n][aria-pressed=true]{background:var(--roxo);border-color:var(--roxo2)}
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
/* ---- rotas ---- */
.galeria{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.rota{background:rgba(11,8,19,.5);border:1px solid var(--bd);border-radius:16px;padding:10px 12px 12px;transition:border-color .15s,transform .15s}
.rota:hover{border-color:var(--roxo2);transform:translateY(-2px)}
.rota svg{width:100%;height:auto;display:block}
.rota .cap{display:flex;justify-content:space-between;gap:8px;font-size:.8rem;margin-top:4px}
.rota .cap b{font-family:var(--mono)}
.mapa{background:radial-gradient(500px 220px at 50% 50%,rgba(139,92,246,.18),transparent 70%),#0d0918;border:1px solid var(--bd);border-radius:16px;padding:6px}
.mapa svg{width:100%;height:auto;display:block}
/* ---- visual de corredor (perfil, provas, medalhas) ---- */
.hero{position:relative;overflow:hidden;border:1px solid var(--bd);border-radius:26px;padding:34px 30px 30px;
background:radial-gradient(700px 320px at 85% -10%,rgba(139,92,246,.45),transparent 65%),linear-gradient(160deg,#1b1233,#0f0a1d)}
.hero>svg{position:absolute;inset:0;width:100%;height:100%}
.hero-in{position:relative;display:grid;grid-template-columns:auto 1fr;gap:24px 28px;align-items:center}
.avatar{width:150px;height:150px;border-radius:50%;padding:5px;background:conic-gradient(from 210deg,#C4B5FD,#56B4E9,#8B6CF4,#C4B5FD)}
.avatar svg{width:100%;height:100%;border-radius:50%;display:block}
.eyebrow{margin:0;font:700 .75rem var(--mono);letter-spacing:.18em;color:var(--roxo2)}
.hero h1{font-size:clamp(2rem,5vw,3.3rem);font-style:italic;margin:4px 0 6px;letter-spacing:-.01em}
.hero-stats{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-top:8px}
.hs{background:rgba(11,8,19,.55);border:1px solid var(--bd);border-radius:16px;padding:12px 16px;backdrop-filter:blur(4px)}
.hs .r{color:var(--mut);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em}
.hs .v{font:700 1.9rem/1.15 var(--mono);color:var(--tx);font-variant-numeric:tabular-nums}
.hs.ouro{border-color:var(--ouro)}.hs.ouro .v{color:var(--ouro)}
h2.t{font-style:italic}
.provas{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.bib{position:relative;display:grid;grid-template-columns:auto 1fr auto;gap:6px 14px;align-items:center;padding:16px 18px 16px 22px;border-radius:14px}
.bib .furos{position:absolute;inset:0;pointer-events:none;border-radius:14px;
background:radial-gradient(circle 4px at 9px 9px,var(--bg) 98%,transparent) ,radial-gradient(circle 4px at calc(100% - 9px) 9px,var(--bg) 98%,transparent),
radial-gradient(circle 4px at 9px calc(100% - 9px),var(--bg) 98%,transparent),radial-gradient(circle 4px at calc(100% - 9px) calc(100% - 9px),var(--bg) 98%,transparent)}
.bib.feita{background:#f1eeff;color:#1a1426;grid-template-columns:auto 1fr}
.bib.feita .num{grid-column:1/-1;display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 14px;text-align:left;
border-top:1px solid rgba(26,20,38,.14);padding-top:9px;margin-top:4px}
.bib.feita .num div{display:flex;flex-direction:column;align-items:flex-start;gap:0}
.bib.feita .num dd{font-size:1.05rem}
.bib.feita .mut,.bib.feita p{color:#4a4268;margin:2px 0 0}
.bib.prox{background:var(--card);border:1px solid var(--bd)}
.bib h3{margin:3px 0 0;font:900 1.05rem/1.15 var(--titulo);font-style:italic;text-transform:uppercase}
.bib p{margin:2px 0 0;font-size:.85rem}
.logo{width:56px;height:56px;flex:none}
.logo-img{width:56px;height:56px;flex:none;object-fit:contain;background:#fff;border-radius:12px;padding:4px}
.avatar img{width:100%;height:100%;border-radius:50%;object-fit:cover;display:block}
.bib .corpo{min-width:0}
.tag{white-space:nowrap;display:inline-block;font:700 .62rem var(--mono);letter-spacing:.1em;padding:2px 8px;border-radius:999px;border:1px solid var(--roxo2);color:var(--roxo2)}
.tag.ok{border-color:#4b32b0;color:#4b32b0}
.conta{display:flex;flex-direction:column;align-items:center;color:var(--ouro);font:700 .7rem var(--mono);text-transform:uppercase}
.conta .n{font-size:2rem;line-height:1;color:var(--ouro)}
.num{margin:0;display:grid;gap:4px;text-align:right}
.num div{display:flex;gap:8px;justify-content:flex-end;align-items:baseline}
.num dt{font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:#6a6190}
.num dd{white-space:nowrap;margin:0;font:700 1rem var(--mono);color:#1a1426}
.medalhas{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}
.medalha{display:flex;flex-direction:column;align-items:center;text-align:center;gap:4px;background:var(--card);border:1px solid var(--bd);border-radius:18px;padding:18px 10px}
.anel{width:104px;height:104px;border-radius:50%;display:grid;place-items:center;
background:radial-gradient(circle at 50% 35%,#2b1f4d,#140d26);border:3px solid var(--ouro);box-shadow:0 0 0 5px rgba(255,210,63,.12),0 0 26px rgba(255,210,63,.18)}
.anel span{font:700 1.1rem var(--mono);color:var(--tx);display:flex;flex-direction:column;align-items:center;line-height:1.1}
.anel small{font-size:.7rem;color:var(--mut);font-weight:400}
.medalha .t1{font:900 .85rem var(--titulo);font-style:italic;text-transform:uppercase}
.medalha .t2{font-size:.78rem;color:var(--mut)}
@media(max-width:560px){.hero-in{grid-template-columns:1fr}.avatar{width:110px;height:110px}.bib{grid-template-columns:auto 1fr}.conta,.num{grid-column:1/-1;flex-direction:row;gap:8px}}

.btn-grupo{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
#atu-status{align-items:center}#atu-status span{flex:1}
dialog#editor{width:min(760px,94vw);max-height:90vh;padding:0;border:1px solid var(--roxo2);border-radius:20px;
background:#150f26;color:var(--tx);box-shadow:0 20px 60px rgba(0,0,0,.6)}
dialog#editor::backdrop{background:rgba(5,3,12,.75)}
.ed-box{padding:20px 22px;max-height:90vh;overflow:auto}
.ed-top{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}
.ed-top h2{margin:0}
.ed-abas{display:flex;gap:8px;margin:6px 0 14px}
.ed-abas button,.ed-btn{font:700 .82rem var(--mono);color:var(--tx);background:rgba(139,92,246,.14);border:1px solid var(--bd);
border-radius:999px;padding:7px 14px;cursor:pointer}
.ed-abas button[aria-pressed=true],.ed-btn.pri{background:var(--roxo);border-color:var(--roxo2)}
.ed-btn.perigo{border-color:#D55181;color:#ffb3cc}
.ed-btn:hover,.ed-abas button:hover{border-color:var(--roxo2)}
.ed-lin{display:grid;grid-template-columns:48px 1fr auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--bd)}
.ed-lin img,.ed-ph{width:48px;height:48px;border-radius:10px;object-fit:contain;background:#fff}
.ed-ph{display:grid;place-items:center;background:rgba(139,92,246,.18);color:var(--mut);font:700 .7rem var(--mono)}
.ed-lin .n{font-weight:700}.ed-lin .d{color:var(--mut);font-size:.82rem}
.ed-acoes{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.ed-form{display:grid;gap:12px;margin-top:8px}
.ed-form label{display:grid;gap:4px;font-size:.85rem;color:var(--mut)}
.ed-form input[type=text],.ed-form input[type=date],.ed-form input[type=number]{font:inherit;color:var(--tx);background:#0d0918;
border:1px solid var(--bd);border-radius:10px;padding:9px 11px}
.ed-form input:focus-visible{outline:2px solid var(--roxo2)}
.ed-prev{width:84px;height:84px;object-fit:contain;background:#fff;border-radius:12px}
.ed-prev.foto{border-radius:50%;object-fit:cover}
.ed-erro{min-height:1.2em;color:#ffb3cc;font-size:.88rem}
.ed-aviso{color:var(--ouro);font-size:.85rem}
.ed-dica{color:var(--mut);font-size:.8rem}
.ed-sec{margin:18px 0 4px;font:900 .8rem var(--titulo);text-transform:uppercase;font-style:italic;color:var(--roxo2)}

.bib.feita{grid-template-columns:auto 1fr}
.bib .mini{grid-column:1/-1;width:100%;height:96px;margin-top:6px;padding:4px;border:1px solid rgba(26,20,38,.25);border-radius:12px;background:#150f26;cursor:pointer}
.bib .mini svg{width:100%;height:100%;display:block}.bib .mini:hover{border-color:var(--roxo)}
.rota[data-det]{cursor:pointer}.rota[data-det]:focus-visible{outline:2px solid var(--roxo2);outline-offset:2px}
dialog#detalhe{width:min(940px,96vw);max-height:92vh;padding:0;border:1px solid var(--roxo2);border-radius:20px;background:#150f26;color:var(--tx);box-shadow:0 20px 60px rgba(0,0,0,.6)}
dialog#detalhe::backdrop{background:rgba(5,3,12,.78)}
.det-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:6px 0 14px}
.det-st{background:rgba(11,8,19,.5);border:1px solid var(--bd);border-radius:12px;padding:8px 12px}
.det-st .r{color:var(--mut);font-size:.7rem;text-transform:uppercase;letter-spacing:.07em}
.det-st .v{font:700 1.1rem var(--mono);font-variant-numeric:tabular-nums}
.det-mapa{background:#0d0918;border:1px solid var(--bd);border-radius:16px;padding:10px;margin-bottom:14px;text-align:center}
.det-mapa svg{width:min(100%,340px);height:auto}
.det-mapa .sub{margin:4px 0 0}
.det-h{font:900 .8rem var(--titulo);text-transform:uppercase;font-style:italic;color:var(--roxo2);margin:10px 0 4px}

.dv.mob,.per.mob{display:none}
@media (max-width:700px){
.dv.desk{display:none}.dv.mob{display:block}
.per.mob .ch text,.dv.mob .ch text{font-size:14px}.per.mob .ch .yl,.dv.mob .ch .yl{font-size:13px}
.per.mob .ch .vl,.dv.mob .ch .vl{font-size:14px}.per.mob .ch .desc{font-size:14px}
.grid{grid-template-columns:repeat(2,1fr)}.kpi .v{font-size:1.7rem}.kpi.s .v{font-size:1.25rem}
.card{padding:14px 12px}main{padding:18px 10px 40px}
.ed-abas{flex-wrap:wrap}.seletor button,.btn-editar,.ed-btn{min-height:40px}
.hero{padding:22px 14px}.hero-in{gap:14px}
}
@media (max-width:640px){.cmp{grid-template-columns:90px repeat(var(--cols),1fr);font-size:.8rem}}
@media print{
:root{--bg:#fff;--card:#fff;--bd:#c9c4d8;--tx:#1a1426;--mut:#5a5370;--ouro:#9a7400;--roxo:#6a4bd8;
--roxo2:#4b32b0;--sep:#fff;--grade:#ddd}
html,body{background:#fff!important;background-image:none!important}
.seletor,.barra,#tip,#velho,#atu-status,dialog#editor,dialog#detalhe{display:none!important}
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
  document.querySelectorAll('.seletor button[data-n]').forEach(function(b){
    b.setAttribute('aria-pressed',b.getAttribute('data-n')===String(n)?'true':'false');});
  var h=corpo.getAttribute('data-hoje').split('-'),f=new Date(+h[0],+h[1]-1,+h[2]);
  f.setDate(f.getDate()-(n-1));var corte=iso(f);
  document.querySelectorAll('tr[data-d]').forEach(function(tr){tr.hidden=tr.getAttribute('data-d')<corte;});
  tip.style.display='none';
}
document.querySelectorAll('.seletor button[data-n]').forEach(function(b){
  b.addEventListener('click',function(){periodo(+b.getAttribute('data-n'));});});
var n0=+corpo.getAttribute('data-n');if(window.matchMedia&&matchMedia('(max-width:700px)').matches)n0=7;
periodo(n0);

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

EDITOR_JS = """
(function(){
var cfg=window.EDITOR||null,dlg=document.getElementById('editor'),btn=document.getElementById('btn-editar');
if(!btn||!dlg||!dlg.showModal)return;
var box=dlg.querySelector('.ed-box'),estado=null,aba='provas';
function h(tag,at){var e=document.createElement(tag);at=at||{};
  for(var k in at){if(k==='class')e.className=at[k];else if(k==='text')e.textContent=at[k];
    else if(k.indexOf('on')===0)e.addEventListener(k.slice(2),at[k]);else e.setAttribute(k,at[k]);}
  for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c==null)continue;e.appendChild(typeof c==='string'?document.createTextNode(c):c);}return e;}
function api(m,u,c){return fetch(u,{method:m,headers:{'Content-Type':'application/json','X-Token':cfg.token},
  body:c?JSON.stringify(c):undefined}).then(function(r){return r.json().then(function(j){
    if(!r.ok)throw new Error(j.erro||'Não foi possível concluir.');return j;});});}
function dataBr(iso){var p=iso.split('-');return p[2]+'/'+p[1]+'/'+p[0];}
function numBr(v){return v==null?'':String(v).replace('.',',');}
function arq(input){return new Promise(function(ok,no){var f=input.files&&input.files[0];if(!f)return ok(null);
  if(f.size>2500000)return no(new Error('A imagem tem mais de 2,5 MB. Reduza-a e tente de novo.'));
  var ext=(f.name.split('.').pop()||'').toLowerCase();
  if(['png','jpg','jpeg','webp','gif','svg'].indexOf(ext)<0)return no(new Error('Use uma imagem png, jpg, webp, gif ou svg.'));
  var r=new FileReader();r.onload=function(){ok({b64:String(r.result).split(',')[1],ext:ext});};
  r.onerror=function(){no(new Error('Não consegui ler o arquivo.'));};r.readAsDataURL(f);});}
function previa(input,img){input.addEventListener('change',function(){var f=input.files&&input.files[0];
  if(f&&/^image\\//.test(f.type)){img.src=URL.createObjectURL(f);img.hidden=false;}});}
function topo(){return h('div',{class:'ed-top'},h('h2',{id:'ed-t',text:'Editar o painel'}),
  h('button',{type:'button',class:'ed-btn',text:'Fechar',onclick:function(){dlg.close();}}));}
function abas(){return h('div',{class:'ed-abas'},
  h('button',{type:'button','aria-pressed':String(aba==='provas'),text:'Provas',onclick:function(){aba='provas';desenhar();}}),
  h('button',{type:'button','aria-pressed':String(aba==='perfil'),text:'Perfil',onclick:function(){aba='perfil';desenhar();}}),
  h('button',{type:'button','aria-pressed':String(aba==='metas'),text:'Metas',onclick:function(){aba='metas';desenhar();}}),
  h('button',{type:'button','aria-pressed':String(aba==='ajustes'),text:'Ajustes',onclick:function(){aba='ajustes';desenhar();}}));}
function ajuda(){box.textContent='';box.appendChild(topo());
  box.appendChild(h('p',{text:'Esta página foi aberta direto do arquivo, e o navegador não deixa um arquivo gravar nada nem buscar dados novos por conta própria.'}));
  box.appendChild(h('p',{text:'Para editar ou atualizar daqui, abra o painel pelo atalho "Abrir painel" (abrir_painel.bat), que liga isso só neste computador.'}));
  dlg.showModal();}
function carregar(){return api('GET','/api/estado').then(function(e){estado=e;desenhar();}).catch(function(e){
  box.textContent='';box.appendChild(topo());box.appendChild(h('p',{class:'ed-erro',text:e.message}));});}
function salvou(j){if(j.aviso){alert(j.aviso);}location.reload();}
function desenhar(){box.textContent='';box.appendChild(topo());box.appendChild(abas());
  box.appendChild(aba==='provas'?listaProvas():aba==='perfil'?formPerfil():aba==='metas'?formMetas():formAjustes());}
function listaProvas(){var w=h('div');
  w.appendChild(h('button',{type:'button',class:'ed-btn pri',text:'+ Adicionar prova',onclick:function(){formProva(null);}}));
  var fut=[],pas=[],hoje=document.body.getAttribute('data-hoje');
  estado.provas.forEach(function(p){(p.data>hoje?fut:pas).push(p);});
  fut.sort(function(a,b){return a.data<b.data?-1:1;});pas.sort(function(a,b){return a.data<b.data?1:-1;});
  [['Próximas',fut],['Já corridas',pas]].forEach(function(g){if(!g[1].length)return;
    w.appendChild(h('div',{class:'ed-sec',text:g[0]}));
    g[1].forEach(function(p){w.appendChild(h('div',{class:'ed-lin'},
      p.logo_uri?h('img',{src:p.logo_uri,alt:'Logo'}):h('div',{class:'ed-ph',text:'sem logo'}),
      h('div',{},h('div',{class:'n',text:p.nome==='*'?'(nome da Garmin)':p.nome}),
        h('div',{class:'d',text:dataBr(p.data)+(p.dist_km?' · '+numBr(p.dist_km)+' km':'')})),
      h('div',{class:'ed-acoes'},
        h('button',{type:'button',class:'ed-btn',text:'✎ Editar',onclick:function(){formProva(p);}}),
        h('button',{type:'button',class:'ed-btn perigo',text:'✕ Apagar',onclick:function(){apagar(p);}}))));});});
  if(!estado.provas.length)w.appendChild(h('p',{class:'ed-dica',text:'Nenhuma prova cadastrada ainda.'}));
  if(estado.garmin&&estado.garmin.length){w.appendChild(h('div',{class:'ed-sec',text:'Competições marcadas na Garmin, sem logo'}));
    estado.garmin.forEach(function(c){w.appendChild(h('div',{class:'ed-lin'},h('div',{class:'ed-ph',text:'Garmin'}),
      h('div',{},h('div',{class:'n',text:c.nome}),h('div',{class:'d',text:dataBr(c.data)+(c.km?' · '+numBr(c.km)+' km':'')})),
      h('div',{class:'ed-acoes'},h('button',{type:'button',class:'ed-btn',text:'Colocar logo',
        onclick:function(){formProva({id:null,data:c.data,nome:'*',dist_km:null,logo:'',so_logo:true});}}))));});}
  return w;}
function apagar(p){if(!confirm('Apagar a prova "'+(p.nome==='*'?'(nome da Garmin)':p.nome)+'"?'))return;
  api('DELETE','/api/provas/'+p.id+'?versao='+encodeURIComponent(estado.versao_provas)).then(salvou).catch(function(e){alert(e.message);});}
function formProva(p){var novo=!p||p.id==null,so=p&&p.so_logo;box.textContent='';box.appendChild(topo());
  var erro=h('div',{class:'ed-erro',role:'alert'}),prev=h('img',{class:'ed-prev',alt:'Prévia do logo',hidden:'hidden'});
  if(p&&p.logo_uri){prev.src=p.logo_uri;prev.hidden=false;}
  var nome=h('input',{type:'text',maxlength:'120',value:p&&p.nome!=='*'?p.nome:(p?p.nome:''),id:'f-nome'});
  var data=h('input',{type:'date',value:p?p.data:'',id:'f-data'});
  var dist=h('input',{type:'text',inputmode:'decimal',maxlength:'8',placeholder:'ex.: 10 ou 21,1',value:p&&p.dist_km?numBr(p.dist_km):'',id:'f-dist'});
  var logo=h('input',{type:'file',accept:'image/*',id:'f-logo'});previa(logo,prev);logo.addEventListener('change',function(){erro.textContent='';});
  var rem=h('input',{type:'checkbox',id:'f-rem'});
  var f=h('form',{class:'ed-form',onsubmit:function(ev){ev.preventDefault();salvarProva();}});
  if(!so){f.appendChild(h('label',{},'Nome da prova',nome));
    f.appendChild(h('div',{class:'ed-dica',text:'Dica: escreva * no nome para usar o nome da atividade na Garmin.'}));
    f.appendChild(h('label',{},'Data da prova',data));f.appendChild(h('label',{},'Distância em km (opcional)',dist));}
  else{f.appendChild(h('p',{text:'Competição: '+dataBr(p.data)+' (o nome vem da Garmin).'}));}
  f.appendChild(h('label',{},'Logo (imagem do seu computador)',logo));f.appendChild(prev);
  if(!novo&&p.logo)f.appendChild(h('label',{},h('span',{},rem,' Remover o logo atual')));
  f.appendChild(erro);
  f.appendChild(h('div',{class:'ed-acoes'},h('button',{type:'submit',class:'ed-btn pri',text:'Salvar'}),
    h('button',{type:'button',class:'ed-btn',text:'Cancelar',onclick:desenhar})));
  box.appendChild(h('div',{class:'ed-sec',text:novo?(so?'Colocar logo':'Nova prova'):'Editar prova'}));box.appendChild(f);
  function salvarProva(){erro.textContent='';arq(logo).then(function(a){
    var c={versao:estado.versao_provas};
    if(!so){c.nome=nome.value;c.data=data.value;c.dist_km=dist.value;}else{c.nome='*';c.data=p.data;}
    if(a){c.logo_b64=a.b64;c.logo_ext=a.ext;}if(rem.checked)c.remover_logo=true;
    return novo?api('POST','/api/provas',c):api('PUT','/api/provas/'+p.id,c);}).then(salvou).catch(function(e){erro.textContent=e.message;});}}
function formMetas(){var erro=h('div',{class:'ed-erro',role:'alert'}),campos={},defs=estado.metas_def||{},f=h('form',{class:'ed-form'});
  f.appendChild(h('p',{class:'ed-dica',text:'As metas são suas. O painel mostra o quanto das corridas da Garmin já foi feito. Deixe em branco para não ter meta.'}));
  Object.keys(defs).forEach(function(k){var d=defs[k],v=(estado.metas||{})[k];
    var i=h('input',{type:'text',inputmode:'decimal',maxlength:'8',placeholder:'sem meta',value:v?numBr(v):''});campos[k]=i;
    f.appendChild(h('label',{},d.rotulo+' ('+d.unidade+', no período: '+d.periodo+')',i));});
  f.appendChild(erro);f.appendChild(h('div',{class:'ed-acoes'},h('button',{type:'submit',class:'ed-btn pri',text:'Salvar metas'})));
  f.addEventListener('submit',function(ev){ev.preventDefault();erro.textContent='';var m={};
    Object.keys(campos).forEach(function(k){m[k]=campos[k].value;});
    api('PUT','/api/metas',{metas:m}).then(salvou).catch(function(e){erro.textContent=e.message;});});return f;}
function formAjustes(){var erro=h('div',{class:'ed-erro',role:'alert'});
  var venc=h('input',{type:'date',value:estado.chave_vence||''});
  var priv=h('input',{type:'text',inputmode:'numeric',maxlength:'4',value:String(estado.privacidade_m)});
  var dias=estado.chave_dias==null?'não informado':(estado.chave_dias<0?'já venceu':'faltam '+estado.chave_dias+' dias');
  var f=h('form',{class:'ed-form'},
    h('div',{class:'ed-sec',text:'Chave da Garmin'}),
    h('p',{class:'ed-dica',text:'A data de vencimento aparece no site do Garmin Connect (Chave de API pessoal, "Expira em"). O painel avisa 14 dias antes. Situação: '+dias+'.'}),
    h('label',{},'Vence em (deixe em branco para remover)',venc),
    h('div',{class:'ed-sec',text:'Privacidade das rotas'}),
    h('p',{class:'ed-dica',text:'Metros cortados do começo e do fim de cada rota desenhada (padrão 300; 0 desliga o corte).'}),
    h('label',{},'Metros cortados',priv),erro,
    h('div',{class:'ed-acoes'},h('button',{type:'submit',class:'ed-btn pri',text:'Salvar ajustes'})));
  f.addEventListener('submit',function(ev){ev.preventDefault();erro.textContent='';
    api('PUT','/api/config',{chave_vence:venc.value,privacidade_m:priv.value}).then(salvou).catch(function(e){erro.textContent=e.message;});});return f;}
var stat=document.getElementById('atu-status'),btnA=document.getElementById('btn-atualizar'),fechaA=document.getElementById('atu-fechar');
function msgA(t,fechar){stat.hidden=false;stat.querySelector('span').textContent=t;fechaA.hidden=!fechar;}
if(fechaA)fechaA.addEventListener('click',function(){stat.hidden=true;});
function acompanhar(){api('GET','/api/atualizacao').then(function(j){
  if(j.estado==='rodando'){msgA('Atualizando… isso pode levar de 1 a 2 minutos. Não feche esta página.');setTimeout(acompanhar,2000);return;}
  if(j.estado==='ok'){msgA('Atualizado! Recarregando…');setTimeout(function(){location.reload();},700);return;}
  msgA('A atualização não funcionou: '+j.mensagem,true);}).catch(function(e){msgA(e.message,true);});}
function atualizarAgora(){if(!cfg){if(!dlg.open)ajuda();return;}
  msgA('Iniciando a atualização…');api('POST','/api/atualizar').then(acompanhar).catch(function(e){msgA(e.message,true);});}
if(btnA)btnA.addEventListener('click',atualizarAgora);
function formPerfil(){var pf=estado.perfil,erro=h('div',{class:'ed-erro',role:'alert'});
  var prev=h('img',{class:'ed-prev foto',alt:'Foto atual',hidden:'hidden'});if(pf.foto_uri){prev.src=pf.foto_uri;prev.hidden=false;}
  var nome=h('input',{type:'text',maxlength:'80',value:pf.nome}),frase=h('input',{type:'text',maxlength:'160',value:pf.frase});
  var foto=h('input',{type:'file',accept:'image/*'});previa(foto,prev);foto.addEventListener('change',function(){erro.textContent='';});
  var f=h('form',{class:'ed-form',onsubmit:function(ev){ev.preventDefault();erro.textContent='';arq(foto).then(function(a){
    var c={versao:estado.versao_perfil,nome:nome.value,frase:frase.value};if(a){c.foto_b64=a.b64;c.foto_ext=a.ext;}
    return api('PUT','/api/perfil',c);}).then(salvou).catch(function(e){erro.textContent=e.message;});}},
    h('label',{},'Seu nome',nome),h('label',{},'Frase (opcional)',frase),h('label',{},'Foto',foto),prev,erro,
    h('div',{class:'ed-acoes'},h('button',{type:'submit',class:'ed-btn pri',text:'Salvar perfil'})));
  return f;}
btn.addEventListener('click',function(){if(!cfg){ajuda();return;}dlg.showModal();carregar();});
})();
"""

DETALHE_JS = """
(function(){
var dlg=document.getElementById('detalhe');if(!dlg||!dlg.showModal)return;
var cont=document.getElementById('det-conteudo'),tit=document.getElementById('det-t'),tip=document.getElementById('tip');
function abrir(id){var t=document.getElementById('det-'+id);if(!t)return;cont.textContent='';
  cont.appendChild(t.content.cloneNode(true));tit.textContent=t.getAttribute('data-titulo')||'';
  if(tip)dlg.appendChild(tip);dlg.showModal();}
dlg.addEventListener('close',function(){if(tip){document.body.appendChild(tip);tip.style.display='none';}});
dlg.addEventListener('click',function(e){if(e.target===dlg)dlg.close();});
dlg.querySelector('.det-fechar').addEventListener('click',function(){dlg.close();});
document.addEventListener('click',function(e){var el=e.target.closest&&e.target.closest('[data-det]');
  if(el&&!dlg.open)abrir(el.getAttribute('data-det'));});
document.addEventListener('keydown',function(e){if((e.key==='Enter'||e.key===' ')&&e.target.matches&&e.target.matches('[data-det]')){
  e.preventDefault();if(!dlg.open)abrir(e.target.getAttribute('data-det'));}});
})();
"""


def pagina(dias, atividades, ini, fim, agora, avisos=None, alertas=None, chave_vence=None,
           historico=None, metas=None, cobertura_ini=None, corredor=None, rotas=None,
           plano_info=None, calendario=None):
    """Devolve (html, nomes_dos_gráficos_omitidos).

    alertas: faixas de destaque no topo (ex.: chave perto de vencer).
    chave_vence: data de vencimento da chave, só informativa, no rodapé.
    historico: todas as atividades guardadas (para os recordes).
    metas: lista de metas do usuário com o progresso (ver metas.progresso).
    cobertura_ini: data (texto ISO) em que começam os dados guardados.
    corredor: perfil, provas e soma do período (ver corredor.montar), ou None.
    calendario: (eventos, buscado_em) do intervals.icu (intervals.proximos), ou None.
    plano_info: {rumo, ciclos, selos, plano, ref_pace} calculado de plano.json, ou None."""
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
    if plano_info and plano_info.get("rumo"):
        blocos.append(card_rumo(plano_info["rumo"]))
    if calendario is not None:
        blocos.append(card_calendario(calendario, hoje))
    blocos.append(cartao("Esta semana × semana passada × média",
                         "corridas · números da Garmin",
                         card_comparacao(comparar_semanas(atividades, hoje, ini))))
    ids_prova = {str(p["atv"]["id"]) for p in (corredor["feitas"] if corredor else [])
                 if p.get("atv") and p["atv"].get("id") is not None}
    secao_r, hero_xy, templates, minis = secao_rotas(rotas, ids_prova)
    if corredor and (corredor["proximas"] or corredor["feitas"]):
        blocos.append(provas_html(corredor, minis))
    if secao_r:
        blocos.append(secao_r)
    if plano_info and plano_info.get("ciclos"):
        blocos.append(card_ciclos(plano_info["ciclos"], hoje))
    if plano_info and plano_info.get("plano"):
        blocos.append(card_plano_prova(plano_info["plano"]))
    blocos.append(cartao("Tempo por esporte — semana atual",
                         f"{intervalo(sem0, sem0 + dt.timedelta(days=6))} · passe o mouse (ou toque) sobre uma fatia",
                         graf_anel(atividades, sem0, sem0 + dt.timedelta(days=6))))

    def por_periodo(fn):
        """Gera o gráfico para cada período, nas versões computador e celular;
        None se não há dado em nenhum."""
        partes = {("desk", n): fn(janela(fim, n)) for n in opcoes}
        with dimensoes(LARG_CEL, PL_CEL, PB_CEL, LIN_CEL):
            for n in opcoes:
                if n in OPCOES_CEL:
                    partes[("mob", n)] = fn(janela(fim, n))
        if all(x is None for x in partes.values()):
            return None
        return "".join(
            f'<div class="per {versao}" data-n="{n}">'
            + (x if x is not None else f'<p class="sd">sem dado nos últimos {n} dias.</p>')
            + "</div>" for (versao, n), x in partes.items())

    def duas_versoes(fn):
        """Gráfico que não depende do período: uma versão para computador e outra para celular."""
        desk = fn()
        if desk is None:
            return None
        with dimensoes(LARG_CEL, PL_CEL, PB_CEL, LIN_CEL):
            mob = fn()
        return f'<div class="dv desk">{desk}</div><div class="dv mob">{mob}</div>'

    def add(nome, titulo, sub, conteudo):
        if conteudo is None:
            omitidos.append(nome)
        else:
            blocos.append(cartao(titulo, sub, conteudo))

    sub = "passe o mouse (ou toque) sobre um dia · use o seletor de período acima"
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
        f"últimas {MAX_SEMANAS} semanas no máximo · passe o mouse (ou toque) sobre uma semana",
        duas_versoes(lambda: graf_dist_semana(atividades, ini, hoje)))
    add("Zonas de FC por semana", "Tempo por zona de frequência cardíaca",
        "por semana · passe o mouse (ou toque) sobre uma semana", duas_versoes(lambda: graf_zonas_semana(atividades, ini, hoje)))

    ref_pace = plano_info and plano_info.get("ref_pace")
    semanas, linhas_at, datas_at, linhas_d, datas_d, classes_at = tabelas(dias, atividades, ini, hoje, ref_pace)
    t_sem = tabela("semanas", ["Semana", "Corridas", "Distância", "Tempo", "Pace médio"], semanas)
    t_at = (tabela("atividades", ["Data", "Esporte", "Nome", "Distância", "Duração", "Pace",
                                  "FC média", "Cadência", "Elevação", "VO2máx", "Equiv. 10 km"],
                   linhas_at, esq=(0, 1, 2), datas=datas_at, classes=classes_at)
            if linhas_at else '<p class="sd">sem dado: nenhuma atividade no período.</p>')
    recs = recordes(historico if historico is not None else atividades)
    if plano_info and plano_info.get("selos"):
        blocos.append(card_selos(plano_info["selos"]))
    legenda_ritmo = ""
    if ref_pace:
        legenda_ritmo = ('<div class="legrow">' + "".join(
            f'<span class="chip"><i class="quad z{i}"></i>{esc(r)}</span>'
            for i, r in ((1, "fácil"), (2, "moderado"), (3, "forte"), (4, "ritmo de prova ou mais rápido"))) +
            '<span class="mut">cor da borda das corridas = ritmo comparado ao seu equivalente em 10 km</span></div>')
    t_mel = ((medalhas_html(recs) + tabela("recordes", ["Recorde", "Valor", "Detalhe", "Dia"], recs, esq=(0, 2)))
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
    if corredor and corredor["perfil"]:
        cabecalho = hero_html(corredor, agora, hero_xy or None).replace("{ini}", ini.strftime("%d/%m/%Y")).replace("{fim}", fim.strftime("%d/%m/%Y"))
    else:
        cabecalho = (f'<div class="top"><h1>Painel Garmin</h1><p class="sub">Período: {ini.strftime("%d/%m/%Y")} a '
                     f'{fim.strftime("%d/%m/%Y")} · atualizado em {agora.strftime("%d/%m/%Y %H:%M")}</p></div>')
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

    detalhe_dialog = ('<dialog id="detalhe" aria-labelledby="det-t"><div class="ed-box"><div class="ed-top">'
                      '<h2 id="det-t"></h2><button type="button" class="ed-btn det-fechar">Fechar</button></div>'
                      '<div id="det-conteudo"></div></div></dialog>' + templates) if templates else ""
    botoes = "".join(f'<button type="button" data-n="{n}" aria-pressed="{"true" if n == padrao else "false"}">{n} dias</button>'
                     for n in opcoes)
    regras = ("@media (min-width:%dpx){" % (GRAFICO_CEL_PX + 1)
              + "".join(f'body[data-n="{n}"] .per.desk[data-n="{n}"]{{display:block}}' for n in opcoes) + "}"
              + "@media (max-width:%dpx){" % GRAFICO_CEL_PX
              + "".join(f'body[data-n="{n}"] .per.mob[data-n="{n}"]{{display:block}}' for n in opcoes if n in OPCOES_CEL)
              + '.seletor button[data-n="30"]{display:none}}')

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel Garmin</title><style>{CSS}{PLANO_CSS}{regras}</style></head>
<body data-n="{padrao}" data-hoje="{hoje.isoformat()}" data-gerado="{agora.strftime('%Y-%m-%dT%H:%M:%S')}"><main>
{cabecalho}

{faixas}
<div class="grid">{kpis}</div>
<div class="seletor" role="group" aria-label="Período dos gráficos e das tabelas diárias">
<span>Período:</span>{botoes}<span class="btn-grupo"><button type="button" id="btn-atualizar" class="btn-editar">↻ Atualizar agora</button><button type="button" id="btn-editar" class="btn-editar">✎ Provas e perfil</button></span></div>
<div class="faixa" id="atu-status" role="status" hidden><b>Atualização</b><span></span><button type="button" class="ed-btn" id="atu-fechar" hidden>Fechar</button></div>
<dialog id="editor" aria-labelledby="ed-t"><div class="ed-box"></div></dialog>
{"".join(blocos)}

<h2 class="t">Semanas — corridas (segunda a domingo)</h2>{t_sem}
<h2 class="t">Atividades</h2>{legenda_ritmo}{t_at}
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
</main>{detalhe_dialog}<div id="tip"></div><!--EDITOR_CFG--><script>{JS}</script><script>{EDITOR_JS}</script><script>{DETALHE_JS}</script><script>{PLANO_JS}</script></body></html>""", omitidos

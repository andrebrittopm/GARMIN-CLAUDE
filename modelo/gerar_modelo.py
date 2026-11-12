"""Gera modelo/modelo_runner.html: MODELO ESTÁTICO do visual "runner".

Tudo aqui é de exemplo (nomes, fotos, logos, provas, tempos e rotas inventados).
Serve só para aprovar o estilo; não lê a Garmin nem usa a sua conta.
Uso: python modelo/gerar_modelo.py
"""
import datetime as dt
import html
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from visual import CSS  # mesmas cores e fontes do painel real  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
HOJE = dt.date.today()
esc = html.escape


# ---------------------------------------------------------------- rotas -----
def rota_pontos(seed, tipo="loop", n=160):
    """Percurso inventado (só para o desenho)."""
    r = random.Random(seed)
    pts = []
    if tipo == "linha":                      # ponto a ponto, tipo orla
        a, b, c = r.uniform(.15, .4), r.uniform(.05, .15), r.uniform(0, 6.28)
        for i in range(n + 1):
            t = i / n
            pts.append((t * 2.4 - 1.2, a * math.sin(5 * t + c) + b * math.sin(13 * t) + .25 * (t - .5)))
        return pts
    a1, a2, a3 = r.uniform(.15, .35), r.uniform(.05, .2), r.uniform(.02, .08)
    k1, k2 = r.choice([2, 3]), r.choice([3, 4, 5])
    p1, p2 = r.uniform(0, 6.28), r.uniform(0, 6.28)
    sx, sy = r.uniform(.85, 1.25), r.uniform(.6, 1.0)
    rot = r.uniform(0, 6.28)
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        rad = 1 + a1 * math.sin(k1 * t + p1) + a2 * math.sin(k2 * t + p2) + a3 * math.sin(7 * t)
        x, y = sx * rad * math.cos(t), sy * rad * math.sin(t)
        pts.append((x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)))
    return pts


def ajustar(pts, w, h, pad=14):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    esc_ = min((w - 2 * pad) / (max(xs) - min(xs) or 1), (h - 2 * pad) / (max(ys) - min(ys) or 1))
    cx_, cy_ = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return [((x - cx_) * esc_ + w / 2, (y - cy_) * esc_ + h / 2) for x, y in pts]


def caminho(pts):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def rota_svg(seed, tipo, uid, w=220, h=150):
    """Rota neon com início e fim 'ocultos' (privacidade) em tracejado."""
    pts = ajustar(rota_pontos(seed, tipo), w, h)
    k = max(2, len(pts) // 14)
    meio, ini, fim = pts[k:-k], pts[:k + 1], pts[-k - 1:]
    return f'''<svg viewBox="0 0 {w} {h}" role="img" aria-label="Rota de exemplo">
<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#C4B5FD"/><stop offset="1" stop-color="#56B4E9"/></linearGradient>
<filter id="b{uid}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3"/></filter></defs>
<path d="{caminho(meio)}" fill="none" stroke="#8B6CF4" stroke-width="6" opacity=".55" filter="url(#b{uid})"/>
<path d="{caminho(meio)}" fill="none" stroke="url(#g{uid})" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
<path d="{caminho(ini)}" fill="none" stroke="#a79fc2" stroke-width="1.6" stroke-dasharray="2 4" opacity=".6"/>
<path d="{caminho(fim)}" fill="none" stroke="#a79fc2" stroke-width="1.6" stroke-dasharray="2 4" opacity=".6"/></svg>'''


def todas_rotas_svg(w=1000, h=380):
    """Muitas rotas de exemplo sobrepostas ao redor de um ponto (o 'bairro')."""
    cores = ["#C4B5FD", "#56B4E9", "#8B6CF4", "#D55181", "#199E70", "#9085E9"]
    ps = []
    for i in range(30):
        tipo = "linha" if i % 7 == 3 else "loop"
        r = random.Random(500 + i)
        bw, bh = r.uniform(110, 360), r.uniform(80, 230)          # tamanho desta rota
        pts = ajustar(rota_pontos(100 + i, tipo), bw, bh, 0)
        dx = w / 2 + r.uniform(-1, 1) * (w / 2 - bw / 2 - 30) * .55 - bw / 2
        dy = h / 2 + r.uniform(-1, 1) * (h / 2 - bh / 2 - 20) * .6 - bh / 2
        q = [(x + dx, y + dy) for x, y in pts]
        ps.append(f'<path d="{caminho(q)}" fill="none" stroke="{cores[i % len(cores)]}" '
                  f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity=".5"/>')
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Todas as rotas sobrepostas (exemplo)" '
            f'style="mix-blend-mode:screen">{"".join(ps)}</svg>')


def arte_topo(w=1200, h=300):
    ps = []
    for i in range(9):
        pts = ajustar(rota_pontos(300 + i, "linha" if i % 3 == 1 else "loop"), 380, 230, 10)
        dx = (i % 5) * 260 - 40
        ps.append(f'<path d="{caminho([(x + dx, y + (i // 5) * 70 - 10) for x, y in pts])}" fill="none" '
                  f'stroke="#8B6CF4" stroke-width="1.6" opacity=".28"/>')
    faixas = "".join(f'<path d="M-50,{h - 20 + k * 14} Q {w / 2},{h - 140 + k * 22} {w + 50},{h - 20 + k * 14}" '
                     f'fill="none" stroke="#C4B5FD" stroke-width="1" opacity="{.22 - k * .03:.2f}"/>' for k in range(5))
    return f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">{"".join(ps)}{faixas}</svg>'


# ------------------------------------------------------------- imagens -----
def foto_exemplo():
    return '''<svg viewBox="0 0 120 120" role="img" aria-label="Espaço para a sua foto">
<defs><linearGradient id="fg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3a2a78"/><stop offset="1" stop-color="#171028"/></linearGradient></defs>
<rect width="120" height="120" fill="url(#fg)"/>
<circle cx="60" cy="44" r="19" fill="#C4B5FD" opacity=".9"/>
<path d="M22 112c3-26 20-38 38-38s35 12 38 38z" fill="#8B6CF4" opacity=".9"/>
<text x="60" y="108" text-anchor="middle" font-family="Courier New,monospace" font-size="8" fill="#ece8f8">SUA FOTO</text></svg>'''


FORMAS = {
    "escudo": '<path d="M30 6 L52 14 V32 C52 44 42 52 30 56 C18 52 8 44 8 32 V14 Z"/>',
    "circulo": '<circle cx="30" cy="30" r="24"/>',
    "hex": '<path d="M30 5 L52 17.5 V42.5 L30 55 L8 42.5 V17.5 Z"/>',
    "losango": '<path d="M30 4 L56 30 L30 56 L4 30 Z"/>',
}


def logo_exemplo(sigla, forma, cor):
    return (f'<svg class="logo" viewBox="0 0 60 60" role="img" aria-label="Logo de exemplo: {esc(sigla)}">'
            f'<g fill="{cor}">{FORMAS[forma]}</g>'
            f'<text x="30" y="35" text-anchor="middle" font-family="Segoe UI Black,Arial Black,sans-serif" '
            f'font-size="15" font-weight="900" fill="#fff" font-style="italic">{esc(sigla)}</text></svg>')


# ------------------------------------------------------------ conteúdo -----
PROXIMAS = [
    ("Corrida de Fim de Ano", "10 km", dt.date(2026, 12, 6), "FA", "escudo", "#D95926"),
    ("Meia da Orla", "21,1 km", dt.date(2027, 3, 21), "MO", "hex", "#3987E5"),
    ("Maratona Exemplo", "42,2 km", dt.date(2027, 5, 30), "ME", "losango", "#199E70"),
]
FEITAS = [
    ("10K Noturna", "10 km", dt.date(2026, 10, 18), "0:49:58", "5:00 /km", "10K", "circulo", "#D55181"),
    ("Trail da Serra", "15 km", dt.date(2026, 9, 27), "1:37:12", "6:29 /km", "TS", "hex", "#199E70"),
    ("Corrida da Primavera", "5 km", dt.date(2026, 8, 9), "0:23:45", "4:45 /km", "CP", "escudo", "#3987E5"),
    ("Meia da Orla", "21,1 km", dt.date(2026, 5, 24), "1:51:52", "5:18 /km", "MO", "hex", "#3987E5"),
    ("Corrida da Cidade", "10 km", dt.date(2026, 3, 15), "0:51:30", "5:09 /km", "CC", "losango", "#9085E9"),
]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def data_txt(d):
    return f"{d.day:02d} {MESES[d.month - 1]} {d.year}"


def card_proxima(nome, dist, d, sig, forma, cor):
    dias = (d - HOJE).days
    return (f'<article class="bib prox"><div class="furos"></div>'
            f'{logo_exemplo(sig, forma, cor)}'
            f'<div class="corpo"><span class="tag">PRÓXIMA · {esc(dist.upper())}</span><h3>{esc(nome)}</h3>'
            f'<p class="mut">{data_txt(d)}</p></div>'
            f'<div class="conta"><span class="n">{dias}</span><span>dias</span></div></article>')


def card_feita(nome, dist, d, tempo, pace, sig, forma, cor):
    return (f'<article class="bib feita"><div class="furos"></div>'
            f'{logo_exemplo(sig, forma, cor)}'
            f'<div class="corpo"><span class="tag ok">CORRIDA · {esc(dist.upper())}</span><h3>{esc(nome)}</h3>'
            f'<p>{data_txt(d)}</p></div>'
            f'<dl class="num"><div><dt>Tempo</dt><dd>{tempo}</dd></div><div><dt>Pace</dt><dd>{pace}</dd></div></dl></article>')


def valor_medalha(v):
    if " " in v:
        n, u = v.split(" ", 1)
        return f"{esc(n)}<small>{esc(u)}</small>"
    return esc(v)


ROTAS = [  # (seed, tipo, data, distância, pace)
    (11, "loop", "qua 11/11", "10,00 km", "5:00 /km"), (12, "linha", "dom 08/11", "8,00 km", "5:50 /km"),
    (13, "loop", "sex 06/11", "12,00 km", "5:25 /km"), (14, "loop", "qua 04/11", "5,00 km", "5:40 /km"),
    (15, "linha", "dom 01/11", "6,00 km", "5:33 /km"), (16, "loop", "sáb 31/10", "7,50 km", "5:21 /km"),
    (17, "loop", "qui 29/10", "9,00 km", "5:12 /km"), (18, "linha", "dom 25/10", "14,00 km", "5:48 /km"),
]
RECORDES = [("1 km", "4:35", "qua 11/11"), ("5 km", "23:45", "sáb 09/08"), ("10 km", "49:58", "dom 18/10"),
            ("Meia maratona", "1:51:52", "dom 24/05"), ("Mais longa", "21,50 km", "dom 24/05")]
SEMANAS = [("14/09", 21.0), ("21/09", 34.5), ("28/09", 39.2), ("05/10", 28.0), ("12/10", 31.5),
           ("19/10", 36.0), ("26/10", 29.0), ("02/11", 25.0), ("09/11", 10.0)]


def barras_semanas():
    w, h, pl, pb = 1000, 250, 50, 40
    topo = 40.0
    larg = (w - pl - 14) / len(SEMANAS)
    out = []
    for t in (0, 10, 20, 30, 40):
        y = 14 + (h - 14 - pb) * (1 - t / topo)
        out.append(f'<line class="gl" x1="{pl}" x2="{w - 14}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="yl" x="{pl - 8}" y="{y + 4:.1f}" text-anchor="end">{t}</text>')
    for i, (rot, v) in enumerate(SEMANAS):
        x = pl + larg * (i + .5)
        alt = v / topo * (h - 14 - pb)
        atual = i == len(SEMANAS) - 1
        out.append(f'<rect x="{x - 28:.1f}" y="{h - pb - alt:.1f}" width="56" height="{alt:.1f}" rx="5" fill="#3987E5"/>')
        out.append(f'<text class="xl{" hoje" if atual else ""}" x="{x:.1f}" y="{h - pb + 16}" text-anchor="middle">sem {rot}</text>')
        out.append(f'<text class="vl" x="{x:.1f}" y="{h - pb + 32}" text-anchor="middle">{str(v).replace(".", ",")} km</text>')
    return f'<svg class="ch" viewBox="0 0 {w} {h}" role="img" aria-label="Distância por semana (exemplo)">{"".join(out)}</svg>'


EXTRA_CSS = """
.mock-tag{display:flex;gap:10px;align-items:center;justify-content:center;text-align:center;margin:0 0 18px;padding:10px 14px;
border:1px dashed var(--ouro);border-radius:12px;color:var(--ouro);font:700 .78rem var(--mono);letter-spacing:.04em;text-transform:uppercase}
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
.provas{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:14px}
.bib{position:relative;display:grid;grid-template-columns:auto 1fr auto;gap:6px 14px;align-items:center;padding:16px 18px 16px 22px;border-radius:14px}
.bib .furos{position:absolute;inset:0;pointer-events:none;border-radius:14px;
background:radial-gradient(circle 4px at 9px 9px,var(--bg) 98%,transparent) ,radial-gradient(circle 4px at calc(100% - 9px) 9px,var(--bg) 98%,transparent),
radial-gradient(circle 4px at 9px calc(100% - 9px),var(--bg) 98%,transparent),radial-gradient(circle 4px at calc(100% - 9px) calc(100% - 9px),var(--bg) 98%,transparent)}
.bib.feita{background:#f1eeff;color:#1a1426}
.bib.feita .mut,.bib.feita p{color:#4a4268;margin:2px 0 0}
.bib.prox{background:var(--card);border:1px solid var(--bd)}
.bib h3{margin:3px 0 0;font:900 1.05rem/1.15 var(--titulo);font-style:italic;text-transform:uppercase}
.bib p{margin:2px 0 0;font-size:.85rem}
.logo{width:56px;height:56px;flex:none}
.tag{display:inline-block;font:700 .62rem var(--mono);letter-spacing:.1em;padding:2px 8px;border-radius:999px;border:1px solid var(--roxo2);color:var(--roxo2)}
.tag.ok{border-color:#4b32b0;color:#4b32b0}
.conta{display:flex;flex-direction:column;align-items:center;color:var(--ouro);font:700 .7rem var(--mono);text-transform:uppercase}
.conta .n{font-size:2rem;line-height:1;color:var(--ouro)}
.num{margin:0;display:grid;gap:4px;text-align:right}
.num div{display:flex;gap:8px;justify-content:flex-end;align-items:baseline}
.num dt{font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:#6a6190}
.num dd{margin:0;font:700 1rem var(--mono);color:#1a1426}
.galeria{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.rota{background:rgba(11,8,19,.5);border:1px solid var(--bd);border-radius:16px;padding:10px 12px 12px;transition:border-color .15s,transform .15s}
.rota:hover{border-color:var(--roxo2);transform:translateY(-2px)}
.rota svg{width:100%;height:auto;display:block}
.rota .cap{display:flex;justify-content:space-between;gap:8px;font-size:.8rem;margin-top:4px}
.rota .cap b{font-family:var(--mono)}
.mapa{background:radial-gradient(500px 220px at 50% 50%,rgba(139,92,246,.18),transparent 70%),#0d0918;border:1px solid var(--bd);border-radius:16px;padding:6px}
.mapa svg{width:100%;height:auto;display:block}
.medalhas{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}
.medalha{display:flex;flex-direction:column;align-items:center;text-align:center;gap:4px;background:var(--card);border:1px solid var(--bd);border-radius:18px;padding:18px 10px}
.anel{width:104px;height:104px;border-radius:50%;display:grid;place-items:center;
background:radial-gradient(circle at 50% 35%,#2b1f4d,#140d26);border:3px solid var(--ouro);box-shadow:0 0 0 5px rgba(255,210,63,.12),0 0 26px rgba(255,210,63,.18)}
.anel span{font:700 1.1rem var(--mono);color:var(--tx);display:flex;flex-direction:column;align-items:center;line-height:1.1}
.anel small{font-size:.7rem;color:var(--mut);font-weight:400}
.medalha .t1{font:900 .85rem var(--titulo);font-style:italic;text-transform:uppercase}
.medalha .t2{font-size:.78rem;color:var(--mut)}
.leg2{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:6px}
.leg2 div{border:1px solid var(--bd);border-radius:14px;padding:12px 14px;font-size:.86rem}
.leg2 b{display:block;margin-bottom:4px;font:900 .8rem var(--titulo);text-transform:uppercase;font-style:italic}
.ver{color:#8fd9b6}.fix{color:var(--ouro)}
@media(max-width:560px){.hero-in{grid-template-columns:1fr}.avatar{width:110px;height:110px}.bib{grid-template-columns:auto 1fr}.conta,.num{grid-column:1/-1;flex-direction:row;gap:8px}}
"""


def gerar():
    prox = "".join(card_proxima(*p) for p in PROXIMAS)
    feitas = "".join(card_feita(*f) for f in FEITAS)
    galeria = "".join(
        f'<div class="rota" title="Exemplo">{rota_svg(s, t, i)}<div class="cap"><span>{d}</span><b>{dist}</b><span class="mut">{p}</span></div></div>'
        for i, (s, t, d, dist, p) in enumerate(ROTAS))
    medalhas = "".join(
        f'<div class="medalha"><div class="anel"><span>{valor_medalha(v)}</span></div><div class="t1">{esc(r)}</div><div class="t2">{d}</div></div>'
        for r, v, d in RECORDES)
    proxima_dias = (PROXIMAS[0][2] - HOJE).days
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel do Corredor - modelo</title><style>{CSS}{EXTRA_CSS}</style></head>
<body data-n="14" data-hoje="{HOJE.isoformat()}"><main>
<div class="mock-tag">Modelo estático · dados, foto, logos, provas e rotas são de EXEMPLO · nada aqui vem da sua conta Garmin</div>

<header class="hero">{arte_topo()}
<div class="hero-in">
<div class="avatar">{foto_exemplo()}</div>
<div><p class="eyebrow">PAINEL DO CORREDOR</p><h1>Seu Nome</h1>
<p class="sub" style="margin:0">Corredor desde 2024 · texto livre que você escolhe</p></div>
<div class="hero-stats">
<div class="hs"><div class="r">Distância no ano</div><div class="v">1.248,6 km</div></div>
<div class="hs"><div class="r">Corridas no ano</div><div class="v">78</div></div>
<div class="hs"><div class="r">Provas já corridas</div><div class="v">{len(FEITAS)}</div></div>
<div class="hs ouro"><div class="r">Próxima prova em</div><div class="v">{proxima_dias} dias</div></div>
</div></div></header>

<div class="grid">
<div class="kpi"><div class="r">Distância total da semana</div><div class="v">10,00 km</div></div>
<div class="kpi"><div class="r">Corridas na semana</div><div class="v">1</div></div>
<div class="kpi s"><div class="r">Tempo correndo</div><div class="v">0:50:00</div></div>
<div class="kpi s"><div class="r">Pace médio</div><div class="v">5:00 /km</div></div></div>

<h2 class="t">Próximas provas</h2><div class="provas">{prox}</div>
<h2 class="t">Provas que já corri</h2><div class="provas">{feitas}</div>

<section class="card"><h2>Meus percursos</h2>
<p class="sub">uma rota por corrida, no estilo neon · o início e o fim ficam tracejados (ocultos) por privacidade</p>
<div class="galeria">{galeria}</div></section>

<section class="card"><h2>Todas as minhas rotas</h2>
<p class="sub">todas as corridas com GPS sobrepostas: onde mais passei fica mais intenso · sem mapa de fundo, sem enviar sua localização a ninguém</p>
<div class="mapa">{todas_rotas_svg()}</div></section>

<h2 class="t">Recordes</h2><div class="medalhas">{medalhas}</div>

<section class="card"><h2>Distância de corrida por semana</h2>
<p class="sub">os gráficos que você já tem continuam, com o mesmo estilo</p>{barras_semanas()}</section>

<section class="card"><h2>O que é real e o que é fixo</h2>
<div class="leg2">
<div><b class="ver">Vem da Garmin</b>Distâncias, tempos, pace, recordes, datas das atividades, rotas (arquivo GPS da atividade) e tudo dos gráficos.</div>
<div><b class="fix">Você fornece</b>Sua foto, o nome, os logos das provas e os dados das provas futuras (nome, data, distância). Textos e imagens, nunca números de desempenho.</div>
<div><b class="fix">O painel calcula</b>"Faltam N dias" e somas (semana, mês, ano). Sem previsão de tempo de prova, sem conselho de treino.</div>
</div></section>
</main></body></html>"""


if __name__ == "__main__":
    caminho_ = os.path.join(AQUI, "modelo_runner.html")
    with open(caminho_, "w", encoding="utf-8") as f:
        f.write(gerar())
    print("Modelo gerado:", caminho_)

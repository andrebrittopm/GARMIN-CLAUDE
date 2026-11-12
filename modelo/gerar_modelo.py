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


from arte import (arte_topo, ajustar, caminho, foto_exemplo, logo_exemplo,  # noqa: E402
                  rota_pontos, rota_svg)


# ---------------------------------------------------------------- rotas -----
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
.galeria{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.rota{background:rgba(11,8,19,.5);border:1px solid var(--bd);border-radius:16px;padding:10px 12px 12px;transition:border-color .15s,transform .15s}
.rota:hover{border-color:var(--roxo2);transform:translateY(-2px)}
.rota svg{width:100%;height:auto;display:block}
.rota .cap{display:flex;justify-content:space-between;gap:8px;font-size:.8rem;margin-top:4px}
.rota .cap b{font-family:var(--mono)}
.mapa{background:radial-gradient(500px 220px at 50% 50%,rgba(139,92,246,.18),transparent 70%),#0d0918;border:1px solid var(--bd);border-radius:16px;padding:6px}
.mapa svg{width:100%;height:auto;display:block}
.leg2{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:6px}
.leg2 div{border:1px solid var(--bd);border-radius:14px;padding:12px 14px;font-size:.86rem}
.leg2 b{display:block;margin-bottom:4px;font:900 .8rem var(--titulo);text-transform:uppercase;font-style:italic}
.ver{color:#8fd9b6}.fix{color:var(--ouro)}
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

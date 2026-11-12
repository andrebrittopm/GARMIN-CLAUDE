"""Peças de arte em SVG puro (sem rede, sem bibliotecas): curvas decorativas,
rotas desenhadas, selos de prova e silhueta de foto."""
import html
import math
import random

esc = html.escape


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


def foto_exemplo(legenda=True):
    rot = '<text x="60" y="108" text-anchor="middle" font-family="Courier New,monospace" font-size="8" fill="#ece8f8">SUA FOTO</text>' if legenda else ''
    return f'''<svg viewBox="0 0 120 120" role="img" aria-label="Espaço para a sua foto">
<defs><linearGradient id="fg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3a2a78"/><stop offset="1" stop-color="#171028"/></linearGradient></defs>
<rect width="120" height="120" fill="url(#fg)"/>
<circle cx="60" cy="44" r="19" fill="#C4B5FD" opacity=".9"/>
<path d="M22 112c3-26 20-38 38-38s35 12 38 38z" fill="#8B6CF4" opacity=".9"/>
{rot}</svg>'''


FORMAS = {
    "escudo": '<path d="M30 6 L52 14 V32 C52 44 42 52 30 56 C18 52 8 44 8 32 V14 Z"/>',
    "circulo": '<circle cx="30" cy="30" r="24"/>',
    "hex": '<path d="M30 5 L52 17.5 V42.5 L30 55 L8 42.5 V17.5 Z"/>',
    "losango": '<path d="M30 4 L56 30 L30 56 L4 30 Z"/>',
}


def logo_exemplo(sigla, forma, cor):
    return (f'<svg class="logo" viewBox="0 0 60 60" role="img" aria-label="Selo {esc(sigla)}">'
            f'<g fill="{cor}">{FORMAS[forma]}</g>'
            f'<text x="30" y="35" text-anchor="middle" font-family="Segoe UI Black,Arial Black,sans-serif" '
            f'font-size="15" font-weight="900" fill="#fff" font-style="italic">{esc(sigla)}</text></svg>')




CORES_SELO = ["#3987E5", "#D95926", "#199E70", "#9085E9", "#D55181", "#7C5CF0"]


def selo_iniciais(nome):
    """Selo no lugar de um logo que não existe: iniciais da prova, cor estável."""
    palavras = [p for p in nome.replace("-", " ").split() if p and p[0].isalnum()]
    sigla = "".join(p[0] for p in palavras[:2]).upper() or "?"
    h = sum(ord(c) for c in nome)
    formas = list(FORMAS)
    return logo_exemplo(sigla, formas[h % len(formas)], CORES_SELO[h % len(CORES_SELO)])


# ----------------------------------------------------------- rotas reais ----
def _caixa(xy):
    xs, ys = [p[0] for p in xy], [p[1] for p in xy]
    return min(xs), max(xs), min(ys), max(ys)


def rota_real_svg(xy, uid, w=220, h=150, rotulo="Rota"):
    """Rota neon a partir de pontos (x, y) já projetados em km."""
    if len(xy) < 2:
        return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(rotulo)}"></svg>'
    pts = ajustar(xy, w, h)
    return (f'''<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(rotulo)}">
<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#C4B5FD"/><stop offset="1" stop-color="#56B4E9"/></linearGradient>
<filter id="b{uid}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3"/></filter></defs>
<path d="{caminho(pts)}" fill="none" stroke="#8B6CF4" stroke-width="6" opacity=".55" filter="url(#b{uid})"/>
<path d="{caminho(pts)}" fill="none" stroke="url(#g{uid})" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>''')


def rotas_sobrepostas_svg(lista_xy, w=1000, h=420, pad=24):
    """Várias rotas no MESMO quadro (mesma escala): onde mais se passa fica mais
    intenso. lista_xy: do mais antigo ao mais recente (o recente fica mais claro)."""
    validas = [xy for xy in lista_xy if len(xy) >= 2]
    if not validas:
        return ""
    todas = [p for xy in validas for p in xy]
    x0, x1, y0, y1 = _caixa(todas)
    esc_ = min((w - 2 * pad) / ((x1 - x0) or 1e-6), (h - 2 * pad) / ((y1 - y0) or 1e-6))
    ox, oy = (w - (x1 - x0) * esc_) / 2 - x0 * esc_, (h - (y1 - y0) * esc_) / 2 - y0 * esc_
    n = len(validas)
    cores = ["#7C5CF0", "#8B6CF4", "#A592F5", "#C4B5FD", "#56B4E9"]
    ps = []
    for i, xy in enumerate(validas):
        cor = cores[min(len(cores) - 1, int(i / max(n - 1, 1) * (len(cores) - 1) + .5))]
        q = [(x * esc_ + ox, y * esc_ + oy) for x, y in xy]
        ps.append(f'<path d="{caminho(q)}" fill="none" stroke="{cor}" stroke-width="1.8" '
                  f'stroke-linecap="round" stroke-linejoin="round" opacity=".42"/>')
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Todas as rotas sobrepostas" '
            f'style="mix-blend-mode:screen">{"".join(ps)}</svg>')


def arte_topo_real(lista_xy, w=1200, h=300):
    """Fundo do topo com as suas rotas reais (apagadas) no lugar das curvas inventadas."""
    ps = []
    for i, xy in enumerate(lista_xy[:9]):
        if len(xy) < 2:
            continue
        pts = ajustar(xy, 380, 230, 10)
        dx = (i % 5) * 260 - 40
        ps.append(f'<path d="{caminho([(x + dx, y + (i // 5) * 70 - 10) for x, y in pts])}" fill="none" '
                  f'stroke="#8B6CF4" stroke-width="1.6" opacity=".28"/>')
    faixas = "".join(f'<path d="M-50,{h - 20 + k * 14} Q {w / 2},{h - 140 + k * 22} {w + 50},{h - 20 + k * 14}" '
                     f'fill="none" stroke="#C4B5FD" stroke-width="1" opacity="{.22 - k * .03:.2f}"/>' for k in range(5))
    return f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">{"".join(ps)}{faixas}</svg>'

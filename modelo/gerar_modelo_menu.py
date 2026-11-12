"""Gera modelo/modelo_menu.html: PROTÓTIPO do menu lateral (dados de exemplo).
Só para aprovar a navegação; não lê a Garmin nem a sua conta.
Uso: python modelo/gerar_modelo_menu.py"""
import html
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, ".."))
from visual import CSS  # noqa: E402
import gerar_modelo as M  # noqa: E402
from arte import foto_exemplo, rota_svg, arte_topo  # noqa: E402

esc = html.escape
IC = {  # ícones simples (traço)
    "geral": '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "provas": '<path d="M5 21V4m0 0h11l-2 4 2 4H5"/>',
    "percursos": '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h6a3 3 0 0 0 0-6h-4a3 3 0 0 1 0-6h6"/>',
    "treino": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "saude": '<path d="M12 21s-7-4.5-9-9a5 5 0 0 1 9-3 5 5 0 0 1 9 3c-2 4.5-9 9-9 9z"/>',
    "tabelas": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/>',
}
VISTAS = [
    ("geral", "Visão geral", None, ["Metas", "Esta semana × anterior"]),
    ("provas", "Provas", "4", ["Próximas provas", "Provas que já corri"]),
    ("percursos", "Percursos", "12", ["Meus percursos", "Todas as minhas rotas"]),
    ("treino", "Treino", None, ["Tempo por esporte", "Treino por dia", "Distância por semana", "Zonas de FC", "Recordes"]),
    ("saude", "Saúde e recuperação", None, ["Sono", "Passos", "Body Battery", "FC de repouso", "VFC", "SpO2", "Hidratação", "Peso"]),
    ("tabelas", "Tabelas", None, ["Semanas", "Atividades", "Dados diários"]),
]

MENU_CSS = """
body{display:block}
.app{display:grid;grid-template-columns:260px 1fr;min-height:100vh}
.menu{position:sticky;top:0;height:100vh;overflow:auto;padding:18px 14px;border-right:1px solid var(--bd);
background:linear-gradient(180deg,rgba(21,15,38,.92),rgba(11,8,19,.92));display:flex;flex-direction:column;gap:14px}
.menu-topo{display:flex;gap:10px;align-items:center;padding:4px 6px 12px;border-bottom:1px solid var(--bd)}
.menu-topo .av{width:44px;height:44px;border-radius:50%;overflow:hidden;flex:none;background:conic-gradient(from 210deg,#C4B5FD,#56B4E9,#8B6CF4,#C4B5FD);padding:2px}
.menu-topo .av svg{width:100%;height:100%;border-radius:50%;display:block}
.menu-topo b{display:block;font:900 .95rem var(--titulo);font-style:italic;text-transform:uppercase}
.menu-topo span{font-size:.72rem;color:var(--mut)}
.menu nav{display:flex;flex-direction:column;gap:4px}
.menu .item{display:flex;align-items:center;gap:10px;width:100%;text-align:left;padding:10px 12px;border:1px solid transparent;border-radius:12px;
background:transparent;color:var(--tx);font:600 .9rem "Segoe UI",system-ui,sans-serif;cursor:pointer}
.menu .item svg{width:19px;height:19px;flex:none;fill:none;stroke:var(--mut);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.menu .item:hover{background:rgba(139,92,246,.12)}
.menu .item[aria-current=page]{background:rgba(139,92,246,.22);border-color:var(--roxo2)}
.menu .item[aria-current=page] svg{stroke:var(--roxo2)}
.menu .item .bd{margin-left:auto;font:700 .7rem var(--mono);color:var(--mut);border:1px solid var(--bd);border-radius:999px;padding:1px 8px}
.menu .subs{display:none;flex-direction:column;margin:2px 0 6px 31px;border-left:1px solid var(--bd)}
.menu .item[aria-current=page]+.subs{display:flex}
.menu .subs a{padding:5px 12px;color:var(--mut);font-size:.82rem;text-decoration:none;border-radius:8px}
.menu .subs a:hover{color:var(--tx);background:rgba(139,92,246,.1)}
.menu-rodape{margin-top:auto;display:flex;flex-direction:column;gap:8px;padding-top:12px;border-top:1px solid var(--bd)}
.menu-rodape button{width:100%;font:700 .8rem var(--mono);color:var(--tx);background:rgba(139,92,246,.12);border:1px solid var(--bd);border-radius:999px;padding:9px 12px;cursor:pointer}
.menu-rodape button:hover{border-color:var(--roxo2)}
.menu-rodape small{color:var(--mut);font-size:.72rem;text-align:center}
.conteudo{min-width:0;padding:22px 26px 56px;max-width:1180px;width:100%;margin:0 auto}
.vista{display:none}.vista.ativa{display:block}
.vista>h1.tit{font:900 1.6rem var(--titulo);font-style:italic;text-transform:uppercase;margin:0 0 4px}
.topo-mobile{display:none}
.mock-tag{margin-bottom:16px}
@media (max-width:860px){
.app{display:block}
.topo-mobile{display:flex;position:sticky;top:0;z-index:20;gap:10px;align-items:center;padding:10px 12px;background:rgba(11,8,19,.96);border-bottom:1px solid var(--bd)}
.topo-mobile button{font:700 .85rem var(--mono);color:var(--tx);background:rgba(139,92,246,.18);border:1px solid var(--roxo2);border-radius:999px;padding:8px 14px;cursor:pointer;min-height:40px}
.topo-mobile .t{font:900 .95rem var(--titulo);font-style:italic;text-transform:uppercase}
.menu{position:fixed;z-index:30;left:0;top:0;width:min(300px,86vw);transform:translateX(-102%);transition:transform .2s;box-shadow:12px 0 40px rgba(0,0,0,.6)}
body.menu-aberto .menu{transform:none}
.veu{display:none;position:fixed;inset:0;z-index:25;background:rgba(5,3,12,.6)}
body.menu-aberto .veu{display:block}
.conteudo{padding:14px 10px 40px}
}
@media (prefers-reduced-motion:reduce){.menu{transition:none}}
@media print{.menu,.topo-mobile,.veu,.mock-tag{display:none!important}.vista{display:block!important}.app{display:block}}
"""

def icone(k):
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{IC[k]}</svg>'

def menu_html():
    itens = []
    for k, nome, badge, subs in VISTAS:
        bd = f'<span class="bd">{badge}</span>' if badge else ""
        links = "".join(f'<a href="#/{k}">{esc(s)}</a>' for s in subs)
        itens.append(f'<button type="button" class="item" data-vista="{k}">{icone(k)}<span>{esc(nome)}</span>{bd}</button>'
                     f'<div class="subs">{links}</div>')
    return f"""<aside class="menu" id="menu" aria-label="Navegação do painel">
<div class="menu-topo"><div class="av">{foto_exemplo(False)}</div><div><b>Seu Nome</b><span>atualizado há 2 h</span></div></div>
<nav>{''.join(itens)}</nav>
<div class="menu-rodape"><button type="button">↻ Atualizar agora</button><button type="button">✎ Provas e perfil</button>
<small>Período dos gráficos: 14 dias</small></div></aside>"""

def card(t, sub, corpo): return f'<section class="card"><h2>{esc(t)}</h2><p class="sub">{esc(sub)}</p>{corpo}</section>'

def barras(): return M.barras_semanas()

def vistas_html():
    kpis = '<div class="grid"><div class="kpi"><div class="r">Distância total da semana</div><div class="v">10,00 km</div></div><div class="kpi"><div class="r">Corridas na semana</div><div class="v">1</div></div><div class="kpi s"><div class="r">Tempo correndo</div><div class="v">0:50:00</div></div><div class="kpi s"><div class="r">Pace médio</div><div class="v">5:00 /km</div></div></div>'
    metas = card("Suas metas", "progresso até hoje", '<div class="metas"><div class="meta-lin"><div class="topo"><b>Distância no mês</b><span class="mut">01/11 a 30/11</span></div><div class="trilho"><i class="enche" style="width:62%"></i></div><div class="txt"><span class="vv">31 de 50 km</span><span class="vv">62%</span></div></div></div>')
    comp = card("Esta semana × semana passada × média", "corridas · números da Garmin", '<p class="sd" style="margin:0">(cartão de comparação, como hoje)</p>')
    hero = f'<header class="hero">{arte_topo()}<div class="hero-in"><div class="avatar">{foto_exemplo(False)}</div><div><p class="eyebrow">PAINEL DO CORREDOR</p><h1>Seu Nome</h1><p class="sub" style="margin:0">Corredor desde 2024</p></div></div></header>'
    prox = '<div class="provas">' + "".join(M.card_proxima(*p) for p in M.PROXIMAS[:2]) + '</div>'
    feit = '<div class="provas">' + "".join(M.card_feita(*f) for f in M.FEITAS[:3]) + '</div>'
    gal = '<div class="galeria">' + "".join(f'<div class="rota">{rota_svg(s, t, i)}<div class="cap"><span>{d}</span><b>{dist}</b><span class="mut">{p}</span></div></div>' for i, (s, t, d, dist, p) in enumerate(M.ROTAS[:6])) + '</div>'
    mapa = f'<div class="mapa">{M.todas_rotas_svg()}</div>'
    tabela = '<div class="tw"><table><thead><tr><th class="e">Data</th><th class="e">Esporte</th><th>Distância</th><th>Duração</th><th>Pace</th></tr></thead><tbody><tr><td class="e">qua 11/11</td><td class="e">Corrida</td><td>10,00 km</td><td>0:50:00</td><td>5:00 /km</td></tr><tr><td class="e">dom 08/11</td><td class="e">Corrida</td><td>8,00 km</td><td>0:46:40</td><td>5:50 /km</td></tr></tbody></table></div>'
    v = {
        "geral": hero + kpis + metas + comp,
        "provas": '<h1 class="tit">Provas</h1><h2 class="t">Próximas provas</h2>' + prox + '<h2 class="t">Provas que já corri</h2>' + feit,
        "percursos": '<h1 class="tit">Percursos</h1>' + card("Meus percursos", "as corridas mais recentes · clique numa rota para ver o detalhe", gal) + card("Todas as minhas rotas", "sobrepostas, na mesma escala", mapa),
        "treino": '<h1 class="tit">Treino</h1>' + card("Distância de corrida por semana", "quilômetros por semana", barras()) + card("Tempo por esporte — semana atual", "anel (como hoje)", '<p class="sd">(anel e legenda, como hoje)</p>') + card("Treino por dia", "(gráfico de colunas por esporte, como hoje)", '<p class="sd">…</p>'),
        "saude": '<h1 class="tit">Saúde e recuperação</h1>' + card("Sono por noite", "profundo, leve e REM", '<p class="sd">(gráfico, como hoje)</p>') + card("Passos por dia", "com a meta da Garmin", '<p class="sd">(gráfico, como hoje)</p>') + '<p class="mut" style="margin:10px 4px">+ Body Battery, FC de repouso, VFC, SpO2, hidratação e peso</p>',
        "tabelas": '<h1 class="tit">Tabelas</h1><h2 class="t">Atividades</h2>' + tabela,
    }
    return "".join(f'<div class="vista" id="v-{k}" role="region" aria-label="{esc(n)}" tabindex="-1">{v[k]}</div>' for k, n, _, _ in VISTAS)

JS = """
(function(){
var itens=document.querySelectorAll('.menu .item'),vistas=document.querySelectorAll('.vista'),tit=document.getElementById('tit-mob');
function lembrar(k){try{localStorage.setItem('vista',k);}catch(e){}}
function ler(){try{return localStorage.getItem('vista');}catch(e){return null;}}
function mostrar(k,foco){var ok=false;vistas.forEach(function(v){var a=v.id==='v-'+k;v.classList.toggle('ativa',a);if(a)ok=true;});
  if(!ok)k='geral',document.getElementById('v-geral').classList.add('ativa');
  itens.forEach(function(b){var a=b.getAttribute('data-vista')===k;if(a)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');
    if(a&&tit)tit.textContent=b.querySelector('span').textContent;});
  lembrar(k);document.body.classList.remove('menu-aberto');scrollTo(0,0);if(foco)document.getElementById('v-'+k).focus({preventScroll:true});}
itens.forEach(function(b){b.addEventListener('click',function(){var k=b.getAttribute('data-vista');history.replaceState(null,'','#/'+k);mostrar(k,true);});});
document.querySelectorAll('.subs a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();var k=a.getAttribute('href').slice(2);history.replaceState(null,'','#/'+k);mostrar(k,true);});});
document.getElementById('btn-menu').addEventListener('click',function(){document.body.classList.toggle('menu-aberto');});
document.getElementById('veu').addEventListener('click',function(){document.body.classList.remove('menu-aberto');});
document.addEventListener('keydown',function(e){if(e.key==='Escape')document.body.classList.remove('menu-aberto');});
var h=(location.hash.match(/^#\\/(\\w+)/)||[])[1];mostrar(h||ler()||'geral',false);
window.addEventListener('hashchange',function(){var k=(location.hash.match(/^#\\/(\\w+)/)||[])[1];if(k)mostrar(k,true);});
})();
"""

def gerar():
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel do Corredor - protótipo do menu</title><style>{CSS}{M.EXTRA_CSS}{MENU_CSS}</style></head>
<body data-n="14" data-hoje="2026-11-12">
<div class="topo-mobile"><button type="button" id="btn-menu" aria-controls="menu" aria-label="Abrir o menu">☰ Menu</button><span class="t" id="tit-mob">Visão geral</span></div>
<div class="veu" id="veu"></div>
<div class="app">{menu_html()}
<main class="conteudo"><div class="mock-tag">Protótipo do menu lateral · dados de EXEMPLO · clique nos itens para navegar</div>{vistas_html()}</main></div>
<script>{JS}</script></body></html>"""

if __name__ == "__main__":
    cam = os.path.join(AQUI, "modelo_menu.html")
    with open(cam, "w", encoding="utf-8") as f:
        f.write(gerar())
    print("Protótipo gerado:", cam)

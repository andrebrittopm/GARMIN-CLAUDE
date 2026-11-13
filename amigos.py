"""Painel para AMIGOS: uma página estática, gerada SEM os dados sensíveis, entregue por um link secreto.

O que entra: nome, foto e frase, totais (distância, corridas, provas), provas, recordes e conquistas.
Nunca entram: sono, frequência cardíaca, Body Battery, VFC, SpO2, peso, hidratação, passos, zonas,
rotas e mapas de GPS, tabela de atividades (os nomes podem revelar lugares), calendário do
intervals.icu, plano de treino, links dos seus perfis e qualquer chave ou senha.
A página é GERADA já sem esses dados (e não apenas escondida). Não tem JavaScript.

O servidor só entrega esse arquivo, em GET, no endereço /<link-secreto>/. Qualquer outro
caminho dá 404. Trocar o link (--amigos-novo-link) invalida o anterior na hora.
"""
import hmac
import os
import re
import secrets
import stat
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ARQ_TOKEN = "token_amigos.txt"
PASTA_PUBLICA = "publico"
CSP = ("default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; "
       "form-action 'none'; frame-ancestors 'none'")


def _caminho_token(pasta):
    return os.path.join(pasta, ARQ_TOKEN)


def caminho_pagina(pasta):
    return os.path.join(pasta, PASTA_PUBLICA, "index.html")


def token(pasta):
    """Link secreto atual ou None se o painel dos amigos está desligado."""
    try:
        with open(_caminho_token(pasta), encoding="utf-8") as f:
            t = f.read().strip()
    except OSError:
        return None
    return t if len(t) >= 30 and re.fullmatch(r"[A-Za-z0-9_-]+", t) else None


def ativo(pasta):
    return token(pasta) is not None


def _gravar_token(pasta, t):
    fd = os.open(_caminho_token(pasta), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(t + "\n")


def ligar(pasta):
    """Liga (cria o link secreto se ainda não existe). Devolve o link."""
    t = token(pasta)
    if t is None:
        t = secrets.token_urlsafe(24)
        _gravar_token(pasta, t)
    return t


def novo_link(pasta):
    """Troca o link secreto: o anterior deixa de funcionar imediatamente."""
    t = secrets.token_urlsafe(24)
    _gravar_token(pasta, t)
    return t


def desligar(pasta):
    """Apaga o link e a página pública."""
    for cam in (_caminho_token(pasta), caminho_pagina(pasta)):
        try:
            os.remove(cam)
        except OSError:
            pass


def salvar_pagina(pasta, html):
    os.makedirs(os.path.join(pasta, PASTA_PUBLICA), exist_ok=True)
    cam = caminho_pagina(pasta)
    tmp = cam + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, cam)


def _handler(pasta):
    class H(BaseHTTPRequestHandler):
        server_version = "Publico"
        sys_version = ""
        timeout = 10                      # conexão lenta ou parada é encerrada

        def log_message(self, *a):        # o link secreto está na URL: nada de registro de acessos
            pass

        def _responder(self, codigo, corpo, tipo="text/html; charset=utf-8"):
            b = corpo.encode("utf-8")
            self.send_response(codigo)
            for k, v in (("Content-Type", tipo), ("Content-Length", str(len(b))), ("Cache-Control", "no-store"),
                         ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                         ("X-Robots-Tag", "noindex, nofollow, noarchive"), ("Content-Security-Policy", CSP)):
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            t = token(pasta)
            caminho = urlparse(self.path).path
            if t and caminho in (f"/{t}", f"/{t}/") and hmac.compare_digest(caminho.strip("/").encode(), t.encode()):
                try:
                    with open(caminho_pagina(pasta), encoding="utf-8") as f:
                        return self._responder(200, f.read())
                except OSError:
                    pass
            return self._responder(404, "<!doctype html><meta charset=utf-8><title>404</title><p>Não encontrado.")

    return H


def criar(pasta, porta=8766):
    """Servidor só em 127.0.0.1 (o Tailscale Funnel entrega ao público, só esta porta)."""
    return ThreadingHTTPServer(("127.0.0.1", porta), _handler(pasta))


def servir(pasta, porta=8766):
    httpd = criar(pasta, porta)
    print(f"Painel dos amigos ligado em 127.0.0.1:{porta} (o link secreto não é mostrado aqui; "
          "use: py garmin_painel.py --amigos-endereco)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0

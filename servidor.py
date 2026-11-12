"""Modo editor: servidor LOCAL para editar provas e perfil direto no painel.

Segurança:
- escuta só em 127.0.0.1 (nunca na rede);
- exige uma senha aleatória (muda a cada abertura), na URL e no cabeçalho X-Token;
- confere o cabeçalho Host (contra DNS rebinding) e o Origin (contra outros sites);
- POST/PUT só com Content-Type application/json (formulários de outros sites não passam);
- limite de tamanho do corpo; respostas sem cache; CSP que só permite o próprio painel;
- só grava via editor.py (provas.txt, perfil.txt, imagens); nada de caminhos vindos do navegador;
- sem log de acesso (a senha aparece na URL); sem internet; não toca na chave da Garmin.
"""
import hmac
import json
import re
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import corredor
import editor

MARCADOR = "<!--EDITOR_CFG-->"
LIMITE_CORPO = 5_000_000
CSP = ("default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; "
       "script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; "
       "frame-ancestors 'none'")
PAGINA_SEM_SENHA = """<!doctype html><meta charset="utf-8"><title>Painel Garmin</title>
<body style="font:16px system-ui;background:#0b0813;color:#ece8f8;padding:40px;max-width:640px">
<h1>Acesso negado</h1><p>Abra o painel pelo atalho <b>Abrir painel</b> (abrir_painel.bat): ele cria
o endereço com a senha desta sessão.</p></body>"""


def criar(pasta, regerar, porta=8765, token=None, garmin=None):
    """Devolve (httpd, token, porta). `regerar()` recria o painel.html sem consultar a Garmin."""
    token = token or secrets.token_urlsafe(24)
    trava = threading.Lock()
    httpd = None
    ultimo_erro = None
    for p in range(porta, porta + 21):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), _handler(pasta, regerar, token, trava, p, garmin))
            porta = p
            break
        except OSError as e:
            ultimo_erro = e
    if httpd is None:
        raise OSError(f"Não consegui abrir uma porta entre {porta} e {porta + 20}: {ultimo_erro}")
    return httpd, token, porta


def _estado(pasta, garmin=None):
    provas, v_provas = editor.listar_provas(pasta)
    for p in provas:
        p["logo_uri"] = corredor.imagem_uri(f"{pasta}/imagens/corridas", p["logo"], [], "logo") if p["logo"] else None
    perfil, v_perfil = editor.ler_perfil(pasta)
    perfil["foto_uri"] = corredor.imagem_uri(f"{pasta}/imagens", perfil["foto"], [], "foto") if perfil["foto"] else None
    ja = {(p["data"]) for p in provas}
    sem_logo = [c for c in (garmin() if garmin else []) if c["data"] not in ja]
    return {"provas": provas, "versao_provas": v_provas, "perfil": perfil, "versao_perfil": v_perfil,
            "garmin": sem_logo}


def _handler(pasta, regerar, token, trava, porta, garmin=None):
    hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
    origens = {f"http://127.0.0.1:{porta}", f"http://localhost:{porta}"}

    class H(BaseHTTPRequestHandler):
        server_version = "PainelLocal"
        sys_version = ""

        def log_message(self, *a):          # a senha está na URL: não registrar acessos
            pass

        # ------------------------------------------------------- utilidades --
        def _cabecalhos(self, tipo, n, extra=None):
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(n))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()

        def _json(self, codigo, obj):
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self._cabecalhos("application/json; charset=utf-8", len(b))
            self.wfile.write(b)

        def _html(self, codigo, texto):
            b = texto.encode("utf-8")
            self.send_response(codigo)
            self._cabecalhos("text/html; charset=utf-8", len(b))
            self.wfile.write(b)

        def _seguro(self):
            """Host e Origin esperados."""
            if self.headers.get("Host", "") not in hosts:
                return False
            org = self.headers.get("Origin")
            return org is None or org in origens

        def _autenticado(self):
            t = self.headers.get("X-Token", "")
            return hmac.compare_digest(t.encode(), token.encode())

        def _corpo(self):
            if "application/json" not in (self.headers.get("Content-Type") or "").lower():
                raise editor.ErroEdicao("Tipo de conteúdo não aceito.", 415)
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise editor.ErroEdicao("Pedido inválido.", 400) from None
            if n > LIMITE_CORPO:
                raise editor.ErroEdicao("Pedido grande demais.", 413)
            try:
                d = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                raise editor.ErroEdicao("Pedido inválido.", 400) from None
            if not isinstance(d, dict):
                raise editor.ErroEdicao("Pedido inválido.", 400)
            return d

        def _api(self, fn):
            """Executa uma operação de edição, recria o painel e responde."""
            if not self._seguro() or not self._autenticado():
                return self._json(403, {"erro": "Acesso negado."})
            try:
                with trava:
                    resultado = fn()
                    aviso = None
                    try:
                        regerar()
                    except Exception as e:      # os dados foram salvos mesmo assim
                        aviso = f"Salvo, mas não consegui recriar o painel agora ({type(e).__name__})."
                return self._json(200, {"ok": True, "aviso": aviso, "resultado": resultado})
            except editor.ErroEdicao as e:
                return self._json(e.codigo, {"erro": str(e)})
            except Exception as e:
                return self._json(500, {"erro": f"Erro inesperado ({type(e).__name__})."})

        def _id(self, rota):
            m = re.fullmatch(r"/api/provas/(\d{1,6})", rota)
            return int(m.group(1)) if m else None

        # ---------------------------------------------------------- métodos --
        def do_GET(self):
            u = urlparse(self.path)
            if not self._seguro():
                return self._html(403, PAGINA_SEM_SENHA)
            if u.path == "/":
                t = (parse_qs(u.query).get("t") or [""])[0]
                if not hmac.compare_digest(t.encode(), token.encode()):
                    return self._html(403, PAGINA_SEM_SENHA)
                try:
                    with open(f"{pasta}/painel.html", encoding="utf-8") as f:
                        pag = f.read()
                except OSError:
                    return self._html(404, "<meta charset=utf-8><p>O painel ainda não foi gerado. Rode a atualização antes.")
                cfg = "<script>window.EDITOR=" + json.dumps({"token": token}) + ";</script>"
                return self._html(200, pag.replace(MARCADOR, cfg, 1))
            if u.path == "/api/estado":
                if not self._autenticado():
                    return self._json(403, {"erro": "Acesso negado."})
                return self._json(200, _estado(pasta, garmin))
            if u.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return None
            return self._json(404, {"erro": "Não encontrado."})

        def do_POST(self):
            if urlparse(self.path).path != "/api/provas":
                return self._json(404, {"erro": "Não encontrado."})
            if not self._seguro() or not self._autenticado():
                return self._json(403, {"erro": "Acesso negado."})
            try:
                d = self._corpo()
            except editor.ErroEdicao as e:
                return self._json(e.codigo, {"erro": str(e)})
            return self._api(lambda: editor.adicionar_prova(pasta, d, d.get("versao")))

        def do_PUT(self):
            rota = urlparse(self.path).path
            if not self._seguro() or not self._autenticado():
                return self._json(403, {"erro": "Acesso negado."})
            try:
                if rota == "/api/perfil":
                    d = self._corpo()
                    return self._api(lambda: editor.salvar_perfil(pasta, d, d.get("versao")))
                pid = self._id(rota)
                if pid is None:
                    return self._json(404, {"erro": "Não encontrado."})
                d = self._corpo()
            except editor.ErroEdicao as e:
                return self._json(e.codigo, {"erro": str(e)})
            return self._api(lambda: editor.editar_prova(pasta, pid, d, d.get("versao")))

        def do_DELETE(self):
            pid = self._id(urlparse(self.path).path)
            if pid is None:
                return self._json(404, {"erro": "Não encontrado."})
            v = (parse_qs(urlparse(self.path).query).get("versao") or [None])[0]
            return self._api(lambda: editor.apagar_prova(pasta, pid, v))

    return H


def servir(pasta, regerar, porta=8765, abrir=True, garmin=None):
    httpd, token, porta = criar(pasta, regerar, porta, garmin=garmin)
    url = f"http://127.0.0.1:{porta}/?t={token}"
    print("Painel com edição ligado (só neste computador).")
    print(f"Endereço: {url}")
    print("Para editar provas e perfil, use o botão ✎ no painel. Para encerrar, feche esta janela (ou Ctrl+C).")
    if abrir:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        httpd.server_close()
    return 0

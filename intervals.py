"""Calendário do intervals.icu (opcional): os "Próximos dias".

Só LEITURA: um único tipo de pedido, GET /api/v1/athlete/<id>/events. Nunca cria, altera
nem apaga nada no intervals.icu. A chave dele fica no cofre do Windows (nome
intervals-icu-api-key), é lida só na hora de usar e nunca é impressa nem gravada em arquivo.
Segurança do pedido: só HTTPS para intervals.icu, sem seguir redirecionamentos (para a chave
não ser reenviada a outro endereço), resposta limitada a 2 MB.

O resultado fica em intervals.json (nesta pasta, só neste computador): o painel desenha o
que está guardado; a busca acontece junto com a atualização. Falhou? Fica o que já estava.
Descrições dos treinos NÃO são guardadas (só nome, tipo, duração e distância).
"""
import base64
import datetime as dt
import json
import os
import urllib.error
import urllib.request

import configuracao

BASE = "https://intervals.icu"
ARQUIVO = "intervals.json"
LIMITE_RESPOSTA = 2_000_000
MAX_EVENTOS = 200
DIAS_ADIANTE = 21
DIAS_ATRAS = 1
CATEGORIAS = {"WORKOUT": "Treino", "NOTE": "Anotação", "RACE_A": "Prova", "RACE_B": "Prova",
              "RACE_C": "Prova", "TARGET": "Meta", "HOLIDAY": "Folga", "SICK": "Doença",
              "INJURED": "Lesão", "SET_EFTP": "Ajuste", "FITNESS_DAYS": "Ajuste", "SEASON_START": "Temporada",
              "SET_FITNESS": "Ajuste"}


class ErroIntervals(Exception):
    """Mensagem segura (nunca contém a chave)."""


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _pedir(base, caminho, params, chave):
    if not (base.startswith("https://intervals.icu") or base.startswith("http://127.0.0.1")):
        raise ErroIntervals("Endereço do intervals.icu não permitido.")
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    cred = base64.b64encode(f"API_KEY:{chave}".encode()).decode()
    req = urllib.request.Request(f"{base}{caminho}?{qs}", method="GET", headers={
        "Authorization": "Basic " + cred, "Accept": "application/json", "User-Agent": "painel-pessoal/1.0"})
    try:
        with urllib.request.build_opener(_SemRedirecionar).open(req, timeout=30) as r:
            dados = r.read(LIMITE_RESPOSTA + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ErroIntervals("O intervals.icu recusou a chave (confira se é a chave de API certa).") from None
        if e.code == 404:
            raise ErroIntervals("O intervals.icu não achou esse atleta (veja o número com --intervals-atleta).") from None
        raise ErroIntervals(f"O intervals.icu respondeu {e.code}.") from None
    except urllib.error.URLError as e:
        raise ErroIntervals(f"Sem conexão com o intervals.icu ({type(e.reason).__name__}).") from None
    except OSError as e:
        raise ErroIntervals(f"Falha de rede com o intervals.icu ({type(e).__name__}).") from None
    if len(dados) > LIMITE_RESPOSTA:
        raise ErroIntervals("A resposta do intervals.icu é maior que o permitido.")
    try:
        return json.loads(dados)
    except ValueError:
        raise ErroIntervals("O intervals.icu respondeu algo que não entendi.") from None


def buscar(chave, atleta, ini, fim, base=BASE):
    """Eventos do calendário entre ini e fim (datas). Só leitura."""
    d = _pedir(base, f"/api/v1/athlete/{atleta}/events",
               {"oldest": ini.isoformat(), "newest": fim.isoformat()}, chave)
    if not isinstance(d, list):
        raise ErroIntervals("O intervals.icu respondeu algo que não entendi.")
    return d


def _pos(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


def normalizar(eventos):
    """Só o que o painel mostra. Sem descrição, sem links, sem identificadores."""
    out = []
    for e in eventos:
        if not isinstance(e, dict):
            continue
        try:
            dia = dt.date.fromisoformat(str(e.get("start_date_local") or "")[:10])
        except ValueError:
            continue
        cat = str(e.get("category") or "").upper()
        out.append({"data": dia.isoformat(),
                    "nome": str(e.get("name") or "").strip()[:80] or "(sem nome)",
                    "categoria": CATEGORIAS.get(cat, "Evento"),
                    "tipo": str(e.get("type") or "")[:30] or None,
                    "dur_s": _pos(e.get("moving_time") or e.get("duration")),
                    "dist_m": _pos(e.get("distance") or e.get("icu_distance"))})
    out.sort(key=lambda x: (x["data"], x["categoria"], x["nome"]))
    return out[:MAX_EVENTOS]


# ------------------------------------------------------------- guardado ----
def caminho(pasta):
    return os.path.join(pasta, ARQUIVO)


def carregar(pasta):
    try:
        with open(caminho(pasta), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get("eventos"), list) else None
    except (OSError, ValueError):
        return None


def salvar(pasta, eventos, agora):
    tmp = caminho(pasta) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"buscado_em": agora.isoformat(timespec="seconds"), "eventos": eventos}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho(pasta))


def atleta(pasta):
    v = str(configuracao.carregar(pasta).get("intervals_atleta") or "0")
    return v if v.replace("i", "", 1).isdigit() else "0"


def definir_atleta(pasta, texto):
    t = texto.strip().lower()
    if not (t.replace("i", "", 1).isdigit() and len(t) <= 12):
        raise ValueError("Use só o número do atleta, como aparece no intervals.icu (ex.: i12345).")
    d = configuracao.carregar(pasta)
    d["intervals_atleta"] = t
    configuracao.salvar(pasta, d)
    return t


def atualizar(pasta, chave, hoje, agora, base=BASE):
    """Busca e guarda os próximos dias. Devolve a quantidade de eventos guardados."""
    ev = normalizar(buscar(chave, atleta(pasta), hoje - dt.timedelta(days=DIAS_ATRAS),
                           hoje + dt.timedelta(days=DIAS_ADIANTE), base))
    salvar(pasta, ev, agora)
    return len(ev)


def proximos(pasta, hoje, dias=14):
    """(eventos dos próximos dias, buscado_em) ou None se nunca foi buscado."""
    d = carregar(pasta)
    if not d:
        return None
    fim = (hoje + dt.timedelta(days=dias - 1)).isoformat()
    return [e for e in d["eventos"] if hoje.isoformat() <= e.get("data", "") <= fim], d.get("buscado_em")

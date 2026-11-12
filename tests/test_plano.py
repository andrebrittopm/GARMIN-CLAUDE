"""Testes do plano.json, do equivalente de Riegel, dos ciclos, dos selos e do plano de prova.
Dados inventados; não usa chave nem conta. Gera tests/saida/painel_plano.html."""
import datetime as dt, json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import plano, garmin_painel as gp, visual

HOJE = dt.date(2026, 11, 12)


def corrida(dias_atras, dist_km, dur_min, tipo="running"):
    d = HOJE - dt.timedelta(days=dias_atras)
    return {"id": 1000 + dias_atras, "data": d.isoformat(), "hora": "07:00", "tipo": tipo, "nome": "x", "evento": None,
            "dist_m": dist_km * 1000.0, "dur_s": dur_min * 60.0, "vel_ms": dist_km * 1000 / (dur_min * 60),
            "fc_media": 150, "cad": 170, "elev_m": 10, "vo2": 50, "zonas": None, "melhores": {}}


HIST = [corrida(2, 10, 50), corrida(9, 5, 24), corrida(20, 3, 20), corrida(40, 14, 90), corrida(80, 8, 48),
        corrida(1, 10, 30, tipo="cycling")]
CICLOS = [{"ciclo": i + 1, "inicio": (dt.date(2026, 10, 8) + dt.timedelta(days=8 * i)).isoformat(),
           "fim": (dt.date(2026, 10, 8) + dt.timedelta(days=8 * i + 7)).isoformat(), "fase": "Base" if i < 4 else "Limiar",
           "teste": None} for i in range(8)]
ALT = [636, 642, 648, 650, 640, 630, 620, 600, 580, 560, 544]
PLANO = {"inicio": "2026-10-08", "prova": {"nome": "Prova X", "data": "2027-07-04", "dist_km": 10, "meta_min": 41.5, "altitude_km": ALT},
         "marcos": [{"data": "2026-12-08", "marco": "Teste", "meta_min": 45.75}], "ciclos": CICLOS,
         "selos": {"longao_km": [10, 12, 14], "equiv_10k_min": [50, 45], "ritmo_s": [300, 240], "ciclo_km": [20, 100]}}


def grava(pasta, d):
    with open(os.path.join(pasta, "plano.json"), "w", encoding="utf-8") as f:
        f.write(d if isinstance(d, str) else json.dumps(d))


with tempfile.TemporaryDirectory() as pasta:
    # 1) leitura e validação
    assert plano.carregar(pasta) is None, "sem arquivo: nada"
    grava(pasta, "isto nao e json"); assert plano.carregar(pasta) is None
    grava(pasta, "[1,2]"); assert plano.carregar(pasta) is None
    grava(pasta, {"prova": {"data": "2027-02-30", "dist_km": 10}}); assert plano.carregar(pasta) is None, "data inválida"
    grava(pasta, " " * 400_000 + "{}"); assert plano.carregar(pasta) is None, "arquivo grande demais"
    ruim = dict(PLANO, prova=dict(PLANO["prova"], altitude_km=[1, 2, 3], meta_min="rápido"), selos={"longao_km": ["a", True, 12]},
                ciclos=CICLOS + [{"inicio": "lixo"}, 5])
    grava(pasta, ruim); p = plano.carregar(pasta)
    assert p["prova"]["altitude_km"] is None and p["prova"]["meta_min"] is None, "campos inválidos são ignorados"
    assert p["selos"]["longao_km"] == [12.0] and len(p["ciclos"]) == 8
    grava(pasta, PLANO); p = plano.carregar(pasta)
    assert p["prova"]["data"] == dt.date(2027, 7, 4) and len(p["prova"]["altitude_km"]) == 11 and len(p["ciclos"]) == 8

    # 2) Riegel
    assert abs(plano.riegel(10000, 3000, 10000) - 3000) < 1e-9
    assert abs(plano.riegel(5000, 24 * 60, 10000) - 24 * 60 * 2 ** 1.06) < 1e-6
    assert plano.equivalente_de(corrida(1, 3, 20)) is None, "abaixo de 5 km não gera equivalente"
    assert plano.equivalente_de(corrida(1, 10, 30, tipo="cycling")) is None, "só corrida"
    eq = plano.melhor_equivalente(HIST)
    assert eq and abs(eq[0] - min(plano.riegel(10000, 3000, 10000), plano.riegel(5000, 1440, 10000),
                                  plano.riegel(14000, 5400, 10000), plano.riegel(8000, 2880, 10000))) < 1e-6
    assert plano.melhor_equivalente([]) is None and plano.melhor_equivalente(HIST, HOJE - dt.timedelta(days=0), HOJE) is None

    # 3) contagem e barra
    c = plano.contagem(p, HIST, HOJE)
    assert c["dias"] == (dt.date(2027, 7, 4) - HOJE).days == 234 and c["meta_s"] == 41.5 * 60 and c["prova_10k"]
    assert c["atual"]
    # início do plano: melhor equivalente nos 60 dias até 08/10 (a corrida de 80 dias atrás = 24/08 está dentro)
    assert c["inicio"] and c["inicio"][2]["id"] == 1000 + 80
    assert c["frac"] is not None and 0 <= c["frac"] <= 1
    c2 = plano.contagem(p, [corrida(150, 10, 50)], HOJE); assert c2["inicio"] is None and c2["atual"] is None and c2["frac"] is None, "sem ponto de partida: sem barra"
    c3 = plano.contagem(p, [corrida(2, 10, 50)], HOJE); assert c3["inicio"][2]["id"] == 1002 and c3["frac"] == 0.0, "sem corrida antes do plano: usa a primeira depois"
    assert plano.contagem(dict(p, prova=None), HIST, HOJE) is None
    assert plano.contagem(p, HIST, dt.date(2027, 7, 5))["dias"] == -1

    # 4) ciclos: km só da Garmin, futuro sem número
    cl = plano.ciclos(p, HIST, HOJE)
    assert cl[0]["situacao"] == "concluído" and cl[-1]["situacao"] == "futuro" and cl[-1]["km"] is None
    assert abs(sum(x["km"] for x in cl if x["km"] is not None) - (10 + 5 + 3)) < 1e-6, "ciclos somam só as corridas depois do início do plano (bicicleta fora)"
    atual = [x for x in cl if x["situacao"] == "atual"]; assert len(atual) == 1

    # 5) selos
    sl = {s["id"]: s for s in plano.selos(p, HIST, cl, HOJE)}
    assert sl["r1"]["feito"] and sl["r1"]["data"] == HIST[4]["data"]
    assert sl["l10"]["feito"] and sl["l10"]["data"] == HIST[3]["data"], "primeira corrida de 10 km ou mais"
    assert sl["l12"]["feito"] and sl["l14"]["feito"], "14 km feito"
    assert sl["e50"]["feito"], "equivalente < 50:00"
    assert sl["e45"]["feito"] is (plano.melhor_equivalente(HIST)[0] <= 45 * 60)
    assert not sl["p240"]["feito"] and 0 < sl["p240"]["pct"] < 1 and "melhor" in sl["p240"]["falta"]
    assert not sl["c100"]["feito"] and sl["c100"]["falta"].startswith("faltam")
    assert not sl["a100"]["feito"] and "faltam" in sl["a100"]["falta"]
    vazio = {s["id"]: s for s in plano.selos(None, [], [], HOJE)}
    assert not vazio["r1"]["feito"] and vazio["r1"]["pct"] == 0 and all(not s["feito"] for s in vazio.values())

    # 6) cor do ritmo
    assert plano.zona_ritmo(300, None) is None and plano.zona_ritmo(None, 300) is None
    assert plano.zona_ritmo(290, 300)[0] == "z4" and plano.zona_ritmo(320, 300)[0] == "z3"
    assert plano.zona_ritmo(360, 300)[0] == "z2" and plano.zona_ritmo(420, 300)[0] == "z1"

    # 7) plano de prova
    for dist in (5, 7, 10, 21, 42):
        pk = plano.plano_km(3000.0, dist)
        assert abs(pk[-1]["acum"] - 3000) < 1e-6 and abs(sum(r["dist"] for r in pk) - dist) < 1e-9
        assert len({round(r["t"] / r["dist"], 6) for r in pk}) == 1, "sem altitude: ritmo uniforme"
    pk = plano.plano_km(2490.0, 10, ALT)
    assert abs(pk[-1]["acum"] - 2490) < 1e-6 and len(pk) == 10
    sub = max(pk, key=lambda r: r["dz"]); des = min(pk, key=lambda r: r["dz"])
    assert sub["t"] > des["t"] and sub["dz"] > 0 > des["dz"], "subida mais lenta que descida"
    assert plano.plano_km(2000, 21.0975)[-1]["dist"] < 0.11 and len(plano.plano_km(2000, 21.0975)) == 22
    bl = plano.blocos_plano(p, HIST, HOJE)
    assert [b["dist"] for b in bl["blocos"]] == [5, 7, 10, 21, 42] and bl["base"]
    b10 = [b for b in bl["blocos"] if b["dist"] == 10][0]
    assert b10["alt"] and [o[0] for o in b10["opcoes"]] == ["Previsão de hoje", "Meta da prova (41:30)"]
    assert all(not b["alt"] and len(b["opcoes"]) == 1 for b in bl["blocos"] if b["dist"] != 10)
    t5 = [b for b in bl["blocos"] if b["dist"] == 5][0]["opcoes"][0][1]; t10 = b10["opcoes"][0][1]
    assert abs(t10 - bl["base"][0]) < 1e-6 and abs(t5 - t10 * 0.5 ** 1.06) < 1e-6
    assert plano.blocos_plano(p, [], HOJE)["base"] is None

    # 8) painel: com plano aparece tudo; sem plano nada muda; plano quebrado não derruba
    ini = HOJE - dt.timedelta(days=29)
    info = gp.montar_plano(pasta, HIST, HOJE)
    assert info and info["rumo"] and info["ciclos"] and info["selos"] and info["plano"] and info["ref_pace"]
    dias = [{"data": (HOJE - dt.timedelta(days=i)).isoformat()} for i in range(30)][::-1]
    chaves = ("passos", "meta_passos", "sono_s", "sono_prof_s", "sono_leve_s", "sono_rem_s", "fc_repouso", "vfc", "fc_min", "fc_max",
              "estresse", "bb_min", "bb_max", "intensidade", "calorias", "respiracao", "spo2", "andares", "peso", "hidrat_ml", "meta_hidrat_ml")
    for x in dias:
        for k in chaves: x.setdefault(k, None)
    agora = dt.datetime(2026, 11, 12, 18, 0)
    pag, _ = visual.pagina(dias, HIST, ini, HOJE, agora, historico=HIST, plano_info=info)
    for trecho in ("Rumo à prova", "234<small> dias</small>", "Trilha dos ciclos", "Conquistas", "Plano de prova — ritmo de cada km",
                   'data-d="42"', "Previsão de hoje", "Meta da prova (41:30)", "ajustado ao relevo", "Equiv. 10 km", "abaixo de 5 km",
                   'class="z', "Riegel", "Riegel costuma dar"):
        assert trecho in pag, trecho
    assert pag.count('class="pl-d') == 5 and pag.count('class="pl-d on"') == 1
    ref_antes, _ = visual.pagina(dias, HIST, ini, HOJE, agora, historico=HIST)
    assert "Rumo à prova" not in ref_antes and "Trilha dos ciclos" not in ref_antes and "Plano de prova" not in ref_antes
    assert "Equiv. 10 km" in ref_antes and 'class="z' not in ref_antes.split("<table")[2], "sem plano: sem cores de ritmo"
    out = os.path.join(os.path.dirname(__file__), "saida"); os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "painel_plano.html"), "w", encoding="utf-8") as f:
        f.write(pag)
    grava(pasta, "{quebrado"); assert gp.montar_plano(pasta, HIST, HOJE) is None
print("TESTES DO PLANO PASSARAM")

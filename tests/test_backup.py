"""Testes da cópia de segurança e da restauração (pasta temporária, dados inventados)."""
import contextlib, datetime as dt, io, os, sys, tempfile, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backup, garmin_painel as gp


def grava(pasta, rel, conteudo=b"x"):
    c = os.path.join(pasta, *rel.split("/")); os.makedirs(os.path.dirname(c), exist_ok=True)
    open(c, "wb").write(conteudo if isinstance(conteudo, bytes) else conteudo.encode())


def nomes(cam):
    with zipfile.ZipFile(cam) as z: return sorted(z.namelist())


with tempfile.TemporaryDirectory() as pasta:
    grava(pasta, "perfil.txt", "nome: Eu\n"); grava(pasta, "provas.txt", "19/07/2026; X; 7;\n"); grava(pasta, "plano.json", "{}")
    grava(pasta, "config_painel.json", "{}"); grava(pasta, "imagens/foto.jpg", b"\xff\xd8"); grava(pasta, "imagens/corridas/l.png", b"png")
    grava(pasta, "imagens/corridas/sub/fundo.png", b"nao entra"); grava(pasta, "imagens/leia.txt", b"nao entra")
    grava(pasta, "dados_brutos.json", "{saude}"); grava(pasta, "rotas.json", "{gps}"); grava(pasta, "garmin_painel.py", "programa")
    grava(pasta, "ultimo_log.txt", "log"); grava(pasta, "intervals.json", "{}")
    grava(pasta, "imagens/grande.png", b"0" * (backup.LIMITE_IMAGEM + 1))

    # 1) criar: só o pessoal; sem dados de saúde por padrão
    cam, itens = backup.criar(pasta, agora=dt.datetime(2026, 11, 12, 10, 0, 0))
    assert os.path.basename(cam) == "pessoal-20261112-100000.zip" and cam.startswith(os.path.join(pasta, "backups_pessoais"))
    assert nomes(cam) == sorted(["LEIA-ME.txt", "config_painel.json", "imagens/corridas/l.png", "imagens/foto.jpg", "perfil.txt", "plano.json", "provas.txt"]), nomes(cam)
    cam2, _ = backup.criar(pasta, True, dt.datetime(2026, 11, 12, 10, 0, 1))
    assert "dados_brutos.json" in nomes(cam2) and "rotas.json" in nomes(cam2) and "garmin_painel.py" not in nomes(cam2) and cam2.endswith("-com-dados.zip")
    assert "ATENÇÃO" in zipfile.ZipFile(cam2).read("LEIA-ME.txt").decode()
    assert not [f for f in os.listdir(os.path.join(pasta, "backups_pessoais")) if f.endswith(".tmp")]

    # 2) restaurar numa pasta nova (como num computador novo)
    with tempfile.TemporaryDirectory() as nova:
        saida = []
        assert backup.restaurar(nova, cam2, perguntar=False, log=saida.append) == 0
        assert open(os.path.join(nova, "perfil.txt")).read() == "nome: Eu\n" and open(os.path.join(nova, "imagens", "corridas", "l.png"), "rb").read() == b"png"
        assert open(os.path.join(nova, "dados_brutos.json")).read() == "{saude}" and not os.path.exists(os.path.join(nova, "backup_restauracao"))
        # restaurar de novo: o que seria substituído vai para backup_restauracao
        open(os.path.join(nova, "perfil.txt"), "w").write("nome: Mudei\n")
        assert backup.restaurar(nova, cam, perguntar=False, log=saida.append, agora=dt.datetime(2026, 11, 14, 8, 0, 0)) == 0
        assert open(os.path.join(nova, "perfil.txt")).read() == "nome: Eu\n"
        assert open(os.path.join(nova, "backup_restauracao", "20261114-080000", "perfil.txt")).read() == "nome: Mudei\n"
        # cancelar não altera nada
        open(os.path.join(nova, "perfil.txt"), "w").write("nome: Outro\n")
        assert backup.restaurar(nova, cam, entrada=lambda p: "n", log=saida.append) == 0 and open(os.path.join(nova, "perfil.txt")).read() == "nome: Outro\n"

    # 3) ZIP malicioso: só os nomes permitidos; nada fora da pasta
    evil = os.path.join(pasta, "evil.zip")
    with zipfile.ZipFile(evil, "w") as z:
        for n in ("perfil.txt", "../fora.txt", "garmin_painel.py", "atualizar.bat", "imagens/../x.png", "imagens/a/b/c.png", "/abs/perfil.txt",
                  "imagens/corridas/ok.png", "imagens/script.exe", "imagens/..\\y.png", "C:/x.png"):
            z.writestr(n, "conteudo")
    boas, ign = backup.conteudo(evil)
    assert sorted(boas) == ["imagens/corridas/ok.png", "perfil.txt"], boas
    assert {"../fora.txt", "garmin_painel.py", "atualizar.bat", "imagens/../x.png", "imagens/a/b/c.png", "/abs/perfil.txt", "imagens/script.exe"} <= set(ign)
    with tempfile.TemporaryDirectory() as raiz:
        alvo = os.path.join(raiz, "pasta"); os.makedirs(alvo)
        backup.restaurar(alvo, evil, perguntar=False, log=lambda *a: None)
        assert sorted(os.listdir(alvo)) == ["imagens", "perfil.txt"] and not os.path.exists(os.path.join(raiz, "fora.txt"))
    # só lixo / não é zip / tamanho declarado grande demais
    lixo = os.path.join(pasta, "lixo.zip")
    with zipfile.ZipFile(lixo, "w") as z: z.writestr("garmin_painel.py", "x")
    for arq, trecho in ((lixo, "nenhum arquivo pessoal"), (os.path.join(pasta, "perfil.txt"), "não é um ZIP")):
        try: backup.restaurar(pasta, arq, perguntar=False, log=lambda *a: None); raise SystemExit("deveria recusar")
        except backup.ErroBackup as e: assert trecho in str(e), str(e)
    assert open(os.path.join(pasta, "garmin_painel.py")).read() == "programa", "o programa nunca é tocado"

    # 4) linha de comando
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rc = gp.main(["--backup-pessoal", "--pasta-dados", pasta])
    assert rc == 0 and "Cópia criada" in buf.getvalue() and "NÃO entram" in buf.getvalue()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rc = gp.main(["--backup-pessoal", "--com-dados", "--pasta-dados", pasta])
    assert rc == 0 and "ATENÇÃO" in buf.getvalue()
    with tempfile.TemporaryDirectory() as vazia:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = gp.main(["--backup-pessoal", "--pasta-dados", vazia])
        assert rc == 1 and "ERRO" in buf.getvalue()
    # rodízio: só os 10 mais recentes (por último, porque apaga os mais antigos)
    for i in range(12): backup.criar(pasta, agora=dt.datetime(2026, 11, 13, 10, 0, i))
    z_ = sorted(os.listdir(os.path.join(pasta, "backups_pessoais"))); assert len(z_) == 10 and z_[-1].startswith("pessoal-20261113-100011")
print("TESTES DO BACKUP PASSARAM")

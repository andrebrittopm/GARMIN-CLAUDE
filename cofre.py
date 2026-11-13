"""Cofre do sistema: chave pessoal e cache do token.

- A CHAVE só é lida (nunca gravada por este programa). Nome: garmin-personal-api-key
- O TOKEN (vale 24 h, gravado em UTF-8 para caber no limite de 2560 bytes) pode ser guardado no cofre do Windows, com o nome
  garmin-personal-api-token, para não pedir um novo a cada execução. Nunca é
  gravado em arquivo. Qualquer falha no cache é ignorada (o programa só pede um
  token novo). Para apagar: Gerenciador de Credenciais ou `--esquecer-token`.
"""
import os
import subprocess
import sys

NOME_CHAVE = "garmin-personal-api-key"
NOME_TOKEN = "garmin-personal-api-token"
NOME_INTERVALS = "intervals-icu-api-key"      # chave do intervals.icu (opcional, só leitura)


class ErroCofre(Exception):
    """Mensagem segura (sem chave nem token)."""


def _estruturas():
    """Estruturas do Windows (testáveis em qualquer sistema)."""
    import ctypes
    from ctypes import wintypes

    dword = ctypes.c_uint32     # DWORD do Windows = 32 bits (fixo, igual em qualquer sistema)

    class FILETIME(ctypes.Structure):
        _fields_ = [("lo", dword), ("hi", dword)]

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", dword), ("Type", dword),
            ("TargetName", ctypes.c_wchar_p), ("Comment", ctypes.c_wchar_p),
            ("LastWritten", FILETIME),
            ("CredentialBlobSize", dword),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", dword), ("AttributeCount", dword),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p), ("UserName", ctypes.c_wchar_p),
        ]
    return ctypes, wintypes, CREDENTIAL


def _win():
    ctypes, wintypes, CREDENTIAL = _estruturas()
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
    adv.CredWriteW.restype = wintypes.BOOL
    adv.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    adv.CredDeleteW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.c_void_p]
    return ctypes, adv, CREDENTIAL


LIMITE_SEGREDO = 2560   # bytes que o cofre do Windows aceita por credencial


def _ler_win(nome, codificacao="utf-16-le"):
    ctypes, adv, CREDENTIAL = _win()
    ptr = ctypes.POINTER(CREDENTIAL)()
    if not adv.CredReadW(nome, 1, 0, ctypes.byref(ptr)):
        return None
    try:
        c = ptr.contents
        bruto = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
        return bruto.decode(codificacao).strip()
    finally:
        adv.CredFree(ptr)


def _gravar_win(nome, valor, codificacao="utf-16-le", usuario="garmin"):
    ctypes, adv, CREDENTIAL = _win()
    dados = valor.encode(codificacao)
    if len(dados) > LIMITE_SEGREDO:
        return False
    buf = (ctypes.c_ubyte * len(dados)).from_buffer_copy(dados)
    c = CREDENTIAL()
    c.Type = 1
    c.TargetName = nome
    c.UserName = usuario
    c.CredentialBlobSize = len(dados)
    c.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
    c.Persist = 2
    return bool(adv.CredWriteW(ctypes.byref(c), 0))


def _apagar_win(nome):
    _, adv, _ = _win()
    return bool(adv.CredDeleteW(nome, 1, 0))


# ------------------------------------------------- Linux (servidor / VPS) ---
def _credencial_linux(nome):
    """Segredo entregue pelo systemd ao serviço (ImportCredential=): fica em
    $CREDENTIALS_DIRECTORY/<nome>, só visível para o próprio serviço. No disco ele está
    criptografado (/etc/credstore.encrypted). Devolve None se não houver."""
    base = os.environ.get("CREDENTIALS_DIRECTORY")
    if not base or "/" in nome or ".." in nome:
        return None
    try:
        with open(os.path.join(base, nome), encoding="utf-8") as f:
            return f.read().strip() or None
    except (OSError, UnicodeDecodeError):
        return None


# ------------------------------------------------------------------ chave ---
def ler_chave():
    """Lê a chave do cofre do sistema. Devolve texto; nunca imprime."""
    if sys.platform == "win32":
        v = _ler_win(NOME_CHAVE)
        if not v:
            raise ErroCofre("Não achei a chave no Gerenciador de Credenciais "
                            f"(nome '{NOME_CHAVE}'). Refaça o passo de guardar a chave.")
        return v
    if sys.platform == "darwin":
        r = subprocess.run(["security", "find-generic-password", "-s",
                            NOME_CHAVE, "-w"], capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            raise ErroCofre(f"Não achei a chave nas Chaves do Mac (nome '{NOME_CHAVE}').")
        return r.stdout.strip()
    if sys.platform.startswith("linux"):
        v = _credencial_linux(NOME_CHAVE)
        if not v:
            raise ErroCofre(f"Não achei a chave da Garmin ('{NOME_CHAVE}') entre as credenciais do serviço. "
                            "Guarde-a com deploy/guardar_chave.sh (veja deploy/LEIA-ME.md).")
        return v
    raise ErroCofre("Sistema não suportado: use Windows, Mac ou Linux (servidor).")


# ------------------------------------------------------------ cache do token -
def ler_token_cache():
    """Texto guardado ou None. Nunca levanta erro."""
    try:
        return _ler_win(NOME_TOKEN, "utf-8") if sys.platform == "win32" else None
    except Exception:
        return None


def gravar_token_cache(valor):
    try:
        return _gravar_win(NOME_TOKEN, valor, "utf-8") if sys.platform == "win32" else False
    except Exception:
        return False


def apagar_token_cache():
    try:
        return _apagar_win(NOME_TOKEN) if sys.platform == "win32" else False
    except Exception:
        return False


# ------------------------------------------------- chave do intervals.icu ---
def ler_chave_intervals():
    """Chave do intervals.icu ou None se não foi guardada. Nunca imprime."""
    try:
        if sys.platform == "win32":
            return _ler_win(NOME_INTERVALS) or None
        if sys.platform.startswith("linux"):
            return _credencial_linux(NOME_INTERVALS)
        return None
    except Exception:
        return None


def gravar_chave_intervals(valor):
    if sys.platform != "win32":
        raise ErroCofre("Guardar a chave do intervals.icu só está pronto para o Windows.")
    if not _gravar_win(NOME_INTERVALS, valor, "utf-16-le", "intervals"):
        raise ErroCofre("O Windows não aceitou guardar a chave.")


def apagar_chave_intervals():
    try:
        return _apagar_win(NOME_INTERVALS) if sys.platform == "win32" else False
    except Exception:
        return False


def ler_area_de_transferencia():
    """Texto copiado (Windows). Usado só para guardar a chave sem você precisar colá-la em lugar nenhum."""
    if sys.platform != "win32":
        raise ErroCofre("Ler a área de transferência só está pronto para o Windows.")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                           capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        raise ErroCofre("Não consegui ler a área de transferência.") from None
    return r.stdout.decode("utf-8", "replace").strip()


def limpar_area_de_transferencia():
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ' '"],
                       capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass

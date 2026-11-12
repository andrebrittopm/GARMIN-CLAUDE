"""Cofre do sistema: chave pessoal e cache do token.

- A CHAVE só é lida (nunca gravada por este programa). Nome: garmin-personal-api-key
- O TOKEN (vale 24 h) pode ser guardado no cofre do Windows, com o nome
  garmin-personal-api-token, para não pedir um novo a cada execução. Nunca é
  gravado em arquivo. Qualquer falha no cache é ignorada (o programa só pede um
  token novo). Para apagar: Gerenciador de Credenciais ou `--esquecer-token`.
"""
import subprocess
import sys

NOME_CHAVE = "garmin-personal-api-key"
NOME_TOKEN = "garmin-personal-api-token"


class ErroCofre(Exception):
    """Mensagem segura (sem chave nem token)."""


def _win():
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
            ("LastWritten", FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
        ]

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


def _ler_win(nome):
    ctypes, adv, CREDENTIAL = _win()
    ptr = ctypes.POINTER(CREDENTIAL)()
    if not adv.CredReadW(nome, 1, 0, ctypes.byref(ptr)):
        return None
    try:
        c = ptr.contents
        bruto = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
        return bruto.decode("utf-16-le").strip()
    finally:
        adv.CredFree(ptr)


def _gravar_win(nome, valor):
    ctypes, adv, CREDENTIAL = _win()
    dados = valor.encode("utf-16-le")
    buf = (ctypes.c_ubyte * len(dados)).from_buffer_copy(dados)
    c = CREDENTIAL()
    c.Type = 1
    c.TargetName = nome
    c.UserName = "garmin"
    c.CredentialBlobSize = len(dados)
    c.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
    c.Persist = 2
    return bool(adv.CredWriteW(ctypes.byref(c), 0))


def _apagar_win(nome):
    _, adv, _ = _win()
    return bool(adv.CredDeleteW(nome, 1, 0))


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
    raise ErroCofre("Sistema não suportado: use Windows ou Mac.")


# ------------------------------------------------------------ cache do token -
def ler_token_cache():
    """Texto guardado ou None. Nunca levanta erro."""
    try:
        return _ler_win(NOME_TOKEN) if sys.platform == "win32" else None
    except Exception:
        return None


def gravar_token_cache(valor):
    try:
        return _gravar_win(NOME_TOKEN, valor) if sys.platform == "win32" else False
    except Exception:
        return False


def apagar_token_cache():
    try:
        return _apagar_win(NOME_TOKEN) if sys.platform == "win32" else False
    except Exception:
        return False

"""Teste do cofre REAL do Windows (Gerenciador de Credenciais).
Usa um nome temporário próprio: nunca mexe na sua chave nem no seu token."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cofre

if sys.platform != "win32":
    print("Pulado: este teste só roda no Windows."); sys.exit(0)

nome = f"garmin-painel-teste-{os.getpid()}"
valor = "token-de-teste-" + "x" * 1500           # ~1.5 mil caracteres, como um JWT
try:
    assert cofre._gravar_win(nome, valor, "utf-8") is True, "não conseguiu gravar"
    assert cofre._ler_win(nome, "utf-8") == valor, "valor lido diferente do gravado"
    assert cofre._gravar_win(nome, "y" * (cofre.LIMITE_SEGREDO + 1), "utf-8") is False, "deveria recusar segredo grande"
    assert cofre._ler_win(nome, "utf-8") == valor, "gravação recusada não pode alterar o valor"
finally:
    cofre._apagar_win(nome)
assert cofre._ler_win(nome, "utf-8") is None, "credencial deveria ter sido apagada"
print("OK: cofre do Windows gravou, leu, recusou excesso e apagou.")

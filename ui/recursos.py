"""Caminhos de recursos tanto no código-fonte quanto no pacote PyInstaller."""
from pathlib import Path
import sys

NOME_MANUAL = "Manual_do_Usuario_ABC_Aprendiz.pdf"


def diretorio_aplicacao() -> Path:
    """Raiz gravável do projeto ou pasta do executável empacotado."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def caminho_recurso(*partes: str) -> Path:
    raiz = Path(getattr(sys, "_MEIPASS", diretorio_aplicacao()))
    return raiz.joinpath(*partes)


def caminho_manual() -> Path:
    """PDF externo: ao lado do executável ou na raiz do código-fonte."""
    return diretorio_aplicacao() / NOME_MANUAL

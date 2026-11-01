"""Caminhos de recursos tanto no código-fonte quanto no pacote PyInstaller."""
from pathlib import Path
import sys


def diretorio_aplicacao() -> Path:
    """Raiz gravável do projeto ou pasta do executável empacotado."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def caminho_recurso(*partes: str) -> Path:
    raiz = Path(getattr(sys, "_MEIPASS", diretorio_aplicacao()))
    return raiz.joinpath(*partes)

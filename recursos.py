"""Caminhos de recursos tanto no código-fonte quanto no pacote PyInstaller."""
from pathlib import Path
import sys


def caminho_recurso(*partes: str) -> Path:
    raiz = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return raiz.joinpath(*partes)

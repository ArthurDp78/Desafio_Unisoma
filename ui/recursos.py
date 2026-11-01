"""Caminhos e preparação de recursos no código-fonte e no pacote PyInstaller."""
from pathlib import Path
import shutil
import sys

NOME_MANUAL = "Manual_do_Usuario_ABC_Aprendiz.pdf"


def diretorio_aplicacao() -> Path:
    """Raiz do projeto ou pasta que contém o executável empacotado."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def caminho_recurso(*partes: str) -> Path:
    """Localiza um recurso no projeto ou na área temporária do PyInstaller."""
    raiz = Path(getattr(sys, "_MEIPASS", diretorio_aplicacao()))
    return raiz.joinpath(*partes)


def caminho_manual() -> Path:
    """Caminho da cópia persistente do manual, junto ao executável."""
    return diretorio_aplicacao() / NOME_MANUAL


def garantir_manual() -> Path:
    """Retorna a cópia existente ou extrai o PDF empacotado sem sobrescrever."""
    destino = caminho_manual()
    if destino.is_file():
        return destino

    origem = caminho_recurso(NOME_MANUAL)
    if not origem.is_file():
        raise FileNotFoundError(f"Recurso empacotado não encontrado: {origem}")

    destino.parent.mkdir(parents=True, exist_ok=True)
    with origem.open("rb") as arquivo_origem:
        try:
            # Modo exclusivo impede substituir uma cópia já existente.
            arquivo_destino = destino.open("xb")
        except FileExistsError:
            # Outra chamada pode ter criado o arquivo após a primeira verificação.
            if destino.is_file():
                return destino
            raise

        try:
            with arquivo_destino:
                shutil.copyfileobj(arquivo_origem, arquivo_destino)
        except OSError:
            # O destino só é removido depois que esta chamada o criou.
            try:
                destino.unlink()
            except OSError:
                pass
            raise

    return destino

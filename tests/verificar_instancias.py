"""Verificação opcional dos quatro cenários, sempre sobre cópias temporárias.

Uso: python tests/verificar_instancias.py [dist/ABC_Aprendiz/ABC_Aprendiz.exe]
"""
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from openpyxl import load_workbook

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from apresentacao import processar_planilha


def main():
    executavel = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    for numero in range(1, 5):
        origem = RAIZ / "Dados" / f"instancia_{numero}.xlsx"
        antes = sha256(origem.read_bytes()).hexdigest()
        inicio = time.perf_counter()
        if executavel:
            with tempfile.TemporaryDirectory() as pasta:
                copia = Path(pasta) / origem.name
                shutil.copyfile(origem, copia)
                subprocess.run([str(executavel), str(copia)], check=True, timeout=100)
                livro = load_workbook(copia, read_only=True)
                assert {"Alunos", "Turmas", "Ensalamento", "Inconsistências"}.issubset(livro.sheetnames)
                total = sum(linha[0] is not None for linha in livro["Ensalamento"].iter_rows(min_row=2, max_col=4, values_only=True))
                inconsistencias = sum(linha[0] is not None for linha in livro["Inconsistências"].iter_rows(min_row=2, max_col=3, values_only=True))
                livro.close()
        else:
            resultado = processar_planilha(origem)
            assert sum(resultado.totais.values()) == len(resultado.distribuicao)
            assert sum(sum(s) for s in resultado.sexos.values()) == len(resultado.distribuicao)
            total = len(resultado.distribuicao)
            inconsistencias = len(resultado.inconsistencias)
        assert sha256(origem.read_bytes()).hexdigest() == antes, "A planilha original foi alterada"
        print(f"{origem.name}: {total} alunos, {inconsistencias} avisos, {time.perf_counter() - inicio:.2f}s; entrada preservada", flush=True)


if __name__ == "__main__":
    main()

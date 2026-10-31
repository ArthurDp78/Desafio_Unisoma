"""Adaptação de entrada/saída para a UI; não altera o modelo de ensalamento."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
import unicodedata

import pandas as pd

import ensalamento
from dados import criar_turmas
from metricas import calcular_metricas


def texto_busca(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold())
                   if not unicodedata.combining(c))


def categoria(motivo: str) -> str:
    texto = motivo.casefold()
    if "sem turma" in texto:
        return "Alunos sem turma"
    if "nome duplicado" in texto:
        return "Nomes duplicados"
    if "registro não foi alocado" in texto:
        return "Dados ausentes ou inválidos"
    if "normalizad" in texto:
        return "Dados normalizados"
    return "Outras ocorrências"


@dataclass(frozen=True)
class ResultadoInterface:
    origem: Path
    planilha: bytes
    distribuicao: list[dict]
    inconsistencias: list[dict]
    grupos: dict[str, list[dict]]
    totais: dict[str, int]
    sexos: dict[str, tuple[int, int]]
    sem_turma: int
    metricas: dict

    def relatorio(self) -> str:
        linhas = [self.origem.name, f"{len(self.inconsistencias)} registros de inconsistências", ""]
        if not self.inconsistencias:
            return "\n".join([*linhas, "Nenhuma inconsistência registrada."])
        grupos: dict[str, list[dict]] = OrderedDict()
        for registro in self.inconsistencias:
            grupos.setdefault(categoria(registro["Motivo"]), []).append(registro)
        for nome, registros in grupos.items():
            linhas.extend([f"{nome.upper()} ({len(registros)})", ""])
            for registro in registros:
                linhas.extend([f"{registro['Nome']} · Aba Alunos · Linha(s) {registro['Linha']}",
                               registro["Motivo"], ""])
        return "\n".join(linhas)


def processar_planilha(origem: Path) -> ResultadoInterface:
    origem = Path(origem).resolve()
    # Executa a rotina original em uma cópia. Só a exportação grava no destino
    # escolhido pelo usuário; as abas e a formatação vêm do próprio workbook.
    with tempfile.TemporaryDirectory(prefix="abc_aprendiz_") as pasta:
        copia = Path(pasta) / "instancia.xlsx"
        shutil.copyfile(origem, copia)
        execucao = ensalamento.executar_com_resultado(copia)
        with pd.ExcelFile(copia) as excel:
            resultado_ensalamento = pd.read_excel(excel, sheet_name=ensalamento.ABAS["saida"],
                                         usecols=ensalamento.COLUNAS_SAIDA).dropna(how="all").fillna("").to_dict("records")
            inconsistencias = pd.read_excel(excel, sheet_name=ensalamento.ABAS["erros"],
                                             usecols=["Linha", "Nome", "Motivo"]).dropna(how="all").fillna("").to_dict("records")
        planilha = copia.read_bytes()
    metricas = calcular_metricas(
        alunos=execucao.alunos,
        estrutura=execucao.estrutura,
        saida=execucao.saida,
        nao_alocados=execucao.nao_alocados,
        status_solver=execucao.status_solver,
        valor_objetivo=execucao.valor_objetivo,
    )
    grupos = {nome: [] for _, nome, _ in criar_turmas(execucao.estrutura)}
    distribuicao = []
    nao_alocados = []
    # A planilha completa é preservada para exportação. Os grupos e indicadores
    # de distribuição da interface consideram apenas alunos em turmas reais.
    for registro in resultado_ensalamento:
        turma = registro["Turma"]
        if turma == "SEM TURMA":
            nao_alocados.append(registro)
        elif turma in grupos:
            distribuicao.append(registro)
            grupos[turma].append(registro)
        else:
            raise ValueError(f"Turma desconhecida no resultado do ensalamento: {turma!r}.")
    for registros in grupos.values():
        registros.sort(key=lambda r: texto_busca(r["Nome"]))
    totais = {nome: len(registros) for nome, registros in grupos.items()}
    sexos = {nome: (sum(r["Sexo"] == "M" for r in registros), sum(r["Sexo"] == "F" for r in registros))
             for nome, registros in grupos.items()}
    return ResultadoInterface(origem, planilha, distribuicao, inconsistencias, grupos, totais, sexos,
                              len(nao_alocados), metricas)


def exportar_planilha(resultado: ResultadoInterface, destino: Path) -> Path:
    destino = Path(destino).resolve()
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(prefix="abc_export_", suffix=".xlsx", dir=destino.parent,
                                         delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(resultado.planilha)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    except PermissionError as erro:
        raise PermissionError("Feche a planilha no Excel e tente exportar novamente.") from erro
    finally:
        if temporario is not None and temporario.exists():
            temporario.unlink()
    return destino

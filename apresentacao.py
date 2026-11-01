"""Adaptação de entrada/saída para a UI; não altera o modelo de ensalamento."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from io import BytesIO
import os
from pathlib import Path
import shutil
import tempfile
import unicodedata
from zipfile import BadZipFile

import pandas as pd
from openpyxl import load_workbook

import ensalamento
from dados import criar_turmas
from metricas import calcular_metricas


def formatar_percentual(valor: float) -> str:
    return f"{valor:.1f}%".replace(".", ",")


def texto_diferenca_turmas(amplitude: int) -> str:
    return f"{amplitude} {'alunos' if amplitude > 1 else 'aluno'}"


def texto_variacao_genero(variacao: dict) -> str:
    """Descreve todos os sentidos empatados, sem avaliar a distribuição."""
    if not variacao["turmas"]:
        return "Sem turmas"
    if variacao["quantidade"] == 0:
        return "Equilibrado"
    quantidade = variacao["quantidade"]
    textos = []
    for categoria in variacao["predominancias"]:
        nome = {"mulheres": "mulher", "homens": "homem"}[categoria] if quantidade == 1 else categoria
        textos.append(f"{quantidade} {nome} a mais")
    return " · ".join(textos)


def nome_turma_visual(nome: str) -> str:
    turno, separador, letra = nome.partition(" - ")
    return f"{turno.title()} · {letra}" if separador else nome


def separar_ocorrencias(resultado: ResultadoInterface) -> tuple[list[dict], list[dict]]:
    """Usa os motivos já emitidos pelo processamento, sem alterar o resultado."""
    categorias_aviso = {"Nomes duplicados", "Dados normalizados"}
    avisos, inconsistencias = [], []
    for registro in resultado.inconsistencias:
        destino = avisos if categoria(registro["Motivo"]) in categorias_aviso else inconsistencias
        destino.append(registro)
    return inconsistencias, avisos


def inconsistencias_editaveis(origem: Path, registros: list[dict]) -> list[dict]:
    """Lê valores atuais e expõe somente campos cadastrais corrigíveis por linha."""
    campos = {
        "Nome": ("Informe o nome do aluno.", None),
        "Sexo": ("Selecione um sexo válido.", ("Feminino", "Masculino")),
        "Disponibilidade": ("Selecione Manhã ou Tarde.", ("Manhã", "Tarde")),
    }
    try:
        fonte = BytesIO(origem) if isinstance(origem, bytes) else origem
        livro = load_workbook(fonte, read_only=True, data_only=True)
        try:
            if "Alunos" not in livro.sheetnames:
                return []
            planilha = livro["Alunos"]
            cabecalho = {celula.value: celula.column for celula in planilha[1] if celula.value is not None}
            if not set(campos).issubset(cabecalho):
                return []
            saida = []
            for registro in registros:
                try:
                    linha = int(registro["Linha"])
                except (TypeError, ValueError):
                    continue
                if linha < 2 or linha > planilha.max_row:
                    continue
                atuais = {nome: planilha.cell(linha, coluna).value for nome, coluna in cabecalho.items()
                          if nome in campos}
                corrigiveis = []
                if atuais["Nome"] is None or not str(atuais["Nome"]).strip():
                    corrigiveis.append({"campo": "Nome", "problema": campos["Nome"][0],
                                        "atual": atuais["Nome"], "opcoes": None})
                sexo, _ = ensalamento.valor_sexo(atuais["Sexo"])
                if sexo is None:
                    corrigiveis.append({"campo": "Sexo", "problema": campos["Sexo"][0],
                                        "atual": atuais["Sexo"], "opcoes": campos["Sexo"][1]})
                periodo, _ = ensalamento.valor_periodo(atuais["Disponibilidade"])
                if periodo is None:
                    corrigiveis.append({"campo": "Disponibilidade", "problema": campos["Disponibilidade"][0],
                                        "atual": atuais["Disponibilidade"],
                                        "opcoes": campos["Disponibilidade"][1]})
                saida.append({"registro": registro, "linha": linha, "atuais": atuais, "campos": corrigiveis})
            return saida
        finally:
            livro.close()
    except (OSError, KeyError, ValueError, BadZipFile):
        # Problemas estruturais continuam sob a validação atual da planilha.
        return []


def detalhes_registros_por_linha(planilha_bytes: bytes, linhas: list[int]) -> dict[int, dict]:
    """Devolve os valores atuais da aba Alunos para as linhas pedidas."""
    try:
        livro = load_workbook(BytesIO(planilha_bytes), read_only=True, data_only=True)
    except BadZipFile:
        return {}
    try:
        if "Alunos" not in livro.sheetnames:
            raise ValueError("A aba 'Alunos' não foi encontrada.")
        alunos = livro["Alunos"]
        cabecalho = {celula.value: celula.column for celula in alunos[1] if celula.value is not None}
        faltantes = {"Nome", "Sexo", "Disponibilidade"} - set(cabecalho)
        if faltantes:
            raise ValueError("A estrutura da aba 'Alunos' não pode ser editada pela interface.")
        return {
            linha: {campo: alunos.cell(linha, cabecalho[campo]).value
                    for campo in ("Nome", "Sexo", "Disponibilidade")}
            for linha in linhas if 2 <= linha <= alunos.max_row
        }
    finally:
        livro.close()


@dataclass(frozen=True)
class ResultadoRevalidacao:
    planilha: bytes
    inconsistencias: list[dict]
    alunos_validos: int


def revalidar_correcoes(planilha_bytes: bytes, correcoes: list[dict], exclusoes: list[int] = ()) -> ResultadoRevalidacao:
    """Aplica apenas campos informados e repete a validação atual, sem chamar o solver."""
    livro = load_workbook(BytesIO(planilha_bytes))
    try:
        if "Alunos" not in livro.sheetnames:
            raise ValueError("A aba 'Alunos' não foi encontrada; a estrutura precisa ser corrigida fora da interface.")
        alunos_ws = livro["Alunos"]
        cabecalho = {celula.value: celula.column for celula in alunos_ws[1] if celula.value is not None}
        if not {"Nome", "Sexo", "Disponibilidade"}.issubset(cabecalho):
            raise ValueError("A estrutura da aba 'Alunos' não pode ser corrigida pela interface.")
        for correcao in correcoes:
            linha = int(correcao["linha"])
            if linha < 2 or linha > alunos_ws.max_row:
                raise ValueError(f"A linha {linha} não existe mais na aba 'Alunos'.")
            for campo, valor in correcao["valores"].items():
                if campo == "Nome":
                    valor = str(valor).strip()
                    if not valor:
                        continue
                elif campo == "Sexo" and valor not in {"F", "M"}:
                    raise ValueError(f"Selecione Feminino ou Masculino na linha {linha}.")
                elif campo == "Disponibilidade" and valor not in {"Manhã", "Tarde"}:
                    raise ValueError(f"Selecione Manhã ou Tarde na linha {linha}.")
                elif campo not in {"Nome", "Sexo", "Disponibilidade"}:
                    raise ValueError("Campo não editável para correção.")
                alunos_ws.cell(linha, cabecalho[campo]).value = valor
        for linha in set(map(int, exclusoes)):
            if linha < 2 or linha > alunos_ws.max_row:
                raise ValueError(f"A linha {linha} não existe mais na aba 'Alunos'.")
            for campo in ("Nome", "Sexo", "Disponibilidade"):
                alunos_ws.cell(linha, cabecalho[campo]).value = None
        saida = BytesIO()
        livro.save(saida)
        planilha_corrigida = saida.getvalue()
    finally:
        livro.close()
    with pd.ExcelFile(BytesIO(planilha_corrigida)) as excel:
        ensalamento.ler_estrutura(excel)
        alunos, inconsistencias = ensalamento.ler_alunos(excel, permitir_sem_alunos=True)
    return ResultadoRevalidacao(planilha_corrigida, inconsistencias, len(alunos))


def processar_planilha_bytes(origem: Path, planilha_bytes: bytes) -> ResultadoInterface:
    """Gera distribuição sobre a cópia atual da planilha e preserva o caminho de origem."""
    origem = Path(origem).resolve()
    with tempfile.TemporaryDirectory(prefix="abc_distribuicao_") as pasta:
        copia = Path(pasta) / origem.name
        copia.write_bytes(planilha_bytes)
        resultado = processar_planilha(copia)
        return replace(resultado, origem=origem)


def relatorio_ocorrencias(registros: list[dict], vazio: str) -> str:
    """Texto da seção; títulos e contadores ficam nos widgets da interface."""
    if not registros:
        return vazio
    grupos: dict[str, list[dict]] = OrderedDict()
    for registro in registros:
        grupos.setdefault(categoria(registro["Motivo"]), []).append(registro)
    linhas = []
    for nome, itens in grupos.items():
        linhas.extend([f"{nome.upper()} ({len(itens)})", ""])
        for registro in itens:
            linhas.extend([f"{registro['Nome']} · Aba Alunos · Linha(s) {registro['Linha']}",
                           registro["Motivo"], ""])
    return "\n".join(linhas).rstrip()


def relatorios_interface(resultado: ResultadoInterface) -> tuple[str, str]:
    inconsistencias, avisos = separar_ocorrencias(resultado)
    return (relatorio_ocorrencias(inconsistencias, "Nenhuma inconsistência encontrada."),
            relatorio_ocorrencias(avisos, "Nenhum aviso gerado."))


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

"""Ensalamento UniSoma: modelo inteiro binário resolvido por PuLP/CBC."""
from __future__ import annotations

import sys
import unicodedata
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pulp
from openpyxl import load_workbook

from dados import criar_turmas


ABAS = {"alunos": "Alunos", "turmas": "Turmas", "saida": "Ensalamento", "erros": "Inconsistências"}
COLUNAS_SAIDA = ["Nome", "Sexo", "Disponibilidade", "Turma"]


def chave(valor: object) -> str:
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().upper()
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def valor_periodo(valor: object) -> tuple[str | None, str | None]:
    original = "" if pd.isna(valor) else str(valor).strip()
    norm = chave(original)
    if norm in {"MANHA", "MATUTINO", "MORNING"}:
        aviso = None if original == "Manhã" else f"Disponibilidade '{original}' normalizada para 'Manhã'."
        return "MANHÃ", aviso
    if norm in {"TARDE", "VESPERTINO", "AFTERNOON"}:
        aviso = None if original == "Tarde" else f"Disponibilidade '{original}' normalizada para 'Tarde'."
        return "TARDE", aviso
    return None, None


def valor_sexo(valor: object) -> tuple[str | None, str | None]:
    original = "" if pd.isna(valor) else str(valor).strip()
    norm = chave(original)
    if norm in {"F", "FEMININO"}:
        aviso = None if original == "F" else f"Sexo '{original}' normalizado para 'F'."
        return "F", aviso
    if norm in {"M", "MASCULINO"}:
        aviso = None if original == "M" else f"Sexo '{original}' normalizado para 'M'."
        return "M", aviso
    return None, None


@dataclass(frozen=True)
class Aluno:
    linha: int
    nome: str
    sexo: str
    periodo: str


def ler_estrutura(xls: pd.ExcelFile) -> dict[str, dict[str, int]]:
    if ABAS["turmas"] not in xls.sheet_names:
        raise ValueError("O arquivo precisa conter a aba 'Turmas'.")
    tabela = xls.parse(ABAS["turmas"])
    if not {"Recursos", "Quantidade"}.issubset(tabela.columns):
        raise ValueError("A aba 'Turmas' precisa ter as colunas 'Recursos' e 'Quantidade'.")
    estrutura: dict[str, dict[str, int]] = {"MANHÃ": {}, "TARDE": {}}
    for _, linha in tabela.iterrows():
        recurso = chave(linha["Recursos"])
        if recurso not in {"TURMAS_MANHA", "TURMAS_TARDE", "VAGAS_MANHA", "VAGAS_TARDE"}:
            continue
        if pd.isna(linha["Quantidade"]):
            raise ValueError(f"Quantidade ausente para o recurso '{recurso}'.")
        try:
            numero = int(linha["Quantidade"])
        except (TypeError, ValueError):
            raise ValueError(f"Quantidade inválida para o recurso '{recurso}'.")
        if numero <= 0 or float(linha["Quantidade"]) != numero:
            raise ValueError(f"'{recurso}' deve ser um número inteiro positivo.")
        periodo = "MANHÃ" if recurso.endswith("MANHA") else "TARDE"
        tipo = "turmas" if recurso.startswith("TURMAS") else "vagas"
        estrutura[periodo][tipo] = numero
    for periodo in estrutura:
        if set(estrutura[periodo]) != {"turmas", "vagas"}:
            raise ValueError(f"A aba 'Turmas' precisa definir quantidade de turmas e vagas para {periodo}.")
    return estrutura


def ler_alunos(xls: pd.ExcelFile) -> tuple[list[Aluno], list[dict]]:
    if ABAS["alunos"] not in xls.sheet_names:
        raise ValueError("O arquivo precisa conter a aba 'Alunos'.")
    tabela = xls.parse(ABAS["alunos"])
    esperadas = {"Nome", "Sexo", "Disponibilidade"}
    if not esperadas.issubset(tabela.columns):
        raise ValueError("A aba 'Alunos' deve conter as colunas Nome, Sexo e Disponibilidade.")
    alunos: list[Aluno] = []
    inconsistencias: list[dict] = []
    nomes: dict[str, list[int]] = {}
    for indice, linha in tabela.iterrows():
        excel_linha = indice + 2
        nome = "" if pd.isna(linha["Nome"]) else str(linha["Nome"]).strip()
        sexo, aviso_sexo = valor_sexo(linha["Sexo"])
        periodo, aviso_periodo = valor_periodo(linha["Disponibilidade"])
        if not nome and sexo is None and periodo is None:
            continue  # linhas totalmente vazias do template não são registros de aluno
        problemas = []
        if nome and not pd.isna(linha["Nome"]) and str(linha["Nome"]) != nome:
            problemas.append(f"Nome normalizado de '{linha['Nome']}' para '{nome}'.")
        if not nome:
            problemas.append("Nome ausente; registro não foi alocado.")
        if sexo is None:
            problemas.append(f"Sexo ausente ou inválido ({linha['Sexo']!r}); registro não foi alocado.")
        elif aviso_sexo:
            problemas.append(aviso_sexo + " Valor normalizado e incluído no ensalamento.")
        if periodo is None:
            problemas.append(f"Disponibilidade ausente ou inválida ({linha['Disponibilidade']!r}); registro não foi alocado.")
        elif aviso_periodo:
            problemas.append(aviso_periodo + " Valor normalizado e incluído no ensalamento.")
        if problemas:
            inconsistencias.append({"Linha": excel_linha, "Nome": nome or "(sem nome)", "Motivo": " ".join(problemas)})
        if nome and sexo and periodo:
            alunos.append(Aluno(excel_linha, nome, sexo, periodo))
            nomes.setdefault(chave(nome), []).append(excel_linha)
    for linhas in nomes.values():
        if len(linhas) > 1:
            nome = next(a.nome for a in alunos if a.linha == linhas[0])
            inconsistencias.append({"Linha": ", ".join(map(str, linhas)), "Nome": nome,
                                    "Motivo": "Nome duplicado no cadastro. Pode ser homônimo; todos os registros foram mantidos como alunos distintos."})
    if not alunos:
        raise ValueError("Não há alunos com nome, sexo e disponibilidade válidos.")
    return alunos, inconsistencias


def resolver(alunos: list[Aluno], estrutura: dict[str, dict[str, int]]) -> tuple[list[dict], dict[str, int], list[Aluno], str, float | None]:
    turmas = criar_turmas(estrutura)

    modelo = pulp.LpProblem("Ensalamento_ABC_Aprendiz", pulp.LpMinimize)
    x = {(i, j): pulp.LpVariable(f"x_{i}_{j}", cat="Binary")
         for i, aluno in enumerate(alunos) for j, (p, _, _) in enumerate(turmas) if p == aluno.periodo}
    u = {i: pulp.LpVariable(f"u_{i}", cat="Binary") for i in range(len(alunos))}
    # x_ij só existe para turmas do período disponível; isso equivale a fixar x_ij=0
    # nas turmas incompatíveis. u_i=1 identifica aluno que não conseguiu vaga.
    for i, aluno in enumerate(alunos):
        modelo += pulp.lpSum(x[i, j] for j, (p, _, _) in enumerate(turmas) if p == aluno.periodo) + u[i] == 1
    for j, (periodo, _, capacidade) in enumerate(turmas):
        modelo += pulp.lpSum(x[i, j] for i, aluno in enumerate(alunos) if aluno.periodo == periodo) <= capacidade

    w = {}
    k = {}
    for periodo in ("MANHÃ", "TARDE"):
        alunos_turno = [i for i, a in enumerate(alunos) if a.periodo == periodo]
        turmas_turno = [j for j, t in enumerate(turmas) if t[0] == periodo]
        if not alunos_turno:
            continue
        media_alunos = len(alunos_turno) / len(turmas_turno)
        media_mulheres = sum(alunos[i].sexo == "F" for i in alunos_turno) / len(turmas_turno)
        for j in turmas_turno:
            tamanho = pulp.lpSum(x[i, j] for i in alunos_turno)
            w[j] = pulp.LpVariable(f"w_{j}", lowBound=0)
            modelo += w[j] >= tamanho - media_alunos
            modelo += w[j] >= media_alunos - tamanho
            meninas = pulp.lpSum(x[i, j] for i in alunos_turno if alunos[i].sexo == "F")
            # k_j é o desvio absoluto do número médio de alunas por turma no turno.
            k[j] = pulp.LpVariable(f"k_{j}", lowBound=0)
            modelo += k[j] >= meninas - media_mulheres
            modelo += k[j] >= media_mulheres - meninas
    # Função objetivo conforme o rascunho: min Σk_j + Σw_j + Σu_i.
    modelo += pulp.lpSum(k.values()) + pulp.lpSum(w.values()) + pulp.lpSum(u.values())
    modelo.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
    status = pulp.LpStatus[modelo.status]
    status_solucao = getattr(modelo, "sol_status", None)
    solucao_viavel = status_solucao in {
        getattr(pulp, "LpSolutionOptimal", 1),
        getattr(pulp, "LpSolutionIntegerFeasible", 2),
    }
    if not solucao_viavel:
        raise ValueError(f"O solver não encontrou uma solução viável (status: {status}).")

    saida = []
    nao_alocados = []
    for i, aluno in enumerate(alunos):
        if pulp.value(u[i]) > 0.5:
            nao_alocados.append(aluno)
            continue
        j = next(j for j, t in enumerate(turmas) if t[0] == aluno.periodo and pulp.value(x[i, j]) > 0.5)
        saida.append({"Nome": aluno.nome, "Sexo": aluno.sexo,
                      "Disponibilidade": aluno.periodo.title(), "Turma": turmas[j][1]})
    totais = {nome: sum(item["Turma"] == nome for item in saida) for _, nome, _ in turmas}
    return saida, totais, nao_alocados, status, pulp.value(modelo.objective)


def _escrever_aba(wb, nome: str, cabecalhos: list[str], linhas: list[list[object]]) -> None:
    """Atualiza somente as células da tabela, mantendo a aba, a posição e o estilo."""
    ws = wb[nome] if nome in wb.sheetnames else wb.create_sheet(nome)
    # Limpa somente as colunas da tabela anterior; preserva notas e dados à direita.
    for row in ws.iter_rows(min_row=1, max_row=max(ws.max_row, 1), min_col=1, max_col=len(cabecalhos)):
        for celula in row:
            celula.value = None
    for coluna, valor in enumerate(cabecalhos, start=1):
        ws.cell(row=1, column=coluna, value=valor)
    for indice, valores in enumerate(linhas, start=2):
        for coluna, valor in enumerate(valores, start=1):
            ws.cell(row=indice, column=coluna, value=valor)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{ws.cell(row=max(len(linhas) + 1, 1), column=len(cabecalhos)).coordinate}"


def salvar_resultado_excel(
    arquivo: Path,
    saida: list[dict],
    inconsistencias: list[dict],
    nao_alocados: list[Aluno] | None = None,
) -> None:
    """Grava alocados e alunos sem vaga, preservando os dados de entrada.

    Os não alocados aparecem em Ensalamento com Turma="SEM TURMA". A lista
    ``saida`` do solver continua contendo apenas os alocados, para preservar
    os totais e as métricas da solução.
    """
    caminho = Path(arquivo)
    workbook = load_workbook(caminho)
    temporario: Path | None = None
    try:
        if ABAS["alunos"] not in workbook.sheetnames:
            raise ValueError("A aba 'Alunos' não existe no arquivo selecionado.")
        _escrever_aba(
            workbook, ABAS["saida"], COLUNAS_SAIDA,
            [[registro[coluna] for coluna in COLUNAS_SAIDA] for registro in saida]
            + [[aluno.nome, aluno.sexo, aluno.periodo.title(), "SEM TURMA"]
               for aluno in (nao_alocados or [])],
        )
        _escrever_aba(
            workbook, ABAS["erros"], ["Linha", "Nome", "Motivo"],
            [[item["Linha"], item["Nome"], item["Motivo"]] for item in inconsistencias],
        )

        fd, nome_temporario = tempfile.mkstemp(
            prefix=f"{caminho.stem}_", suffix=".tmp.xlsx", dir=str(caminho.parent)
        )
        os.close(fd)
        temporario = Path(nome_temporario)
        workbook.save(temporario)
    except Exception:
        if temporario and temporario.exists():
            temporario.unlink()
        raise
    finally:
        workbook.close()

    try:
        os.replace(temporario, caminho)
    except PermissionError as erro:
        if temporario and temporario.exists():
            temporario.unlink()
        raise PermissionError("Feche o arquivo no Excel e tente novamente; nenhuma alteração foi gravada.") from erro
    except Exception:
        if temporario and temporario.exists():
            temporario.unlink()
        raise


def executar(arquivo: Path) -> str:
    with pd.ExcelFile(arquivo) as xls:
        estrutura = ler_estrutura(xls)
        alunos, inconsistencias = ler_alunos(xls)
    saida, _, nao_alocados, status, _ = resolver(alunos, estrutura)
    for aluno in nao_alocados:
        inconsistencias.append({
            "Linha": aluno.linha,
            "Nome": aluno.nome,
            "Motivo": (
                f"Aluno sem turma no resultado do modelo (período {aluno.periodo.title()}); "
                "verifique a capacidade e os critérios da função objetivo."
            ),
        })

    if status != "Optimal":
        raise ValueError(
            "O solver encontrou uma solução viável, mas não comprovou que é ótima. "
            "O Excel não foi alterado; tente novamente ou reveja o tempo de resolução."
        )

    salvar_resultado_excel(arquivo, saida, inconsistencias, nao_alocados=nao_alocados)
    return (
        f"Ensalamento concluído e salvo no Excel.\n"
        f"Alunos alocados: {len(saida)} | Sem turma: {len(nao_alocados)}\n"
        f"Inconsistências/avisos registrados: {len(inconsistencias)}."
    )


def interface() -> None:
    from interface_desktop import iniciar

    iniciar()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            print(executar(Path(sys.argv[1])))
        except Exception as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            raise SystemExit(1)
    else:
        interface()

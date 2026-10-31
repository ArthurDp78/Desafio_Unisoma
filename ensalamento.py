"""Ensalamento UniSoma: modelo inteiro binário resolvido por PuLP/CBC."""
from __future__ import annotations

import sys
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd
import pulp


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
    turmas: list[tuple[str, str, int]] = []
    letra = 0
    for periodo in ("MANHÃ", "TARDE"):
        for _ in range(estrutura[periodo]["turmas"]):
            letra_nome = chr(ord("A") + letra)
            turmas.append((periodo, f"{periodo} - {letra_nome}", estrutura[periodo]["vagas"]))
            letra += 1

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


def executar(arquivo: Path) -> str:
    with pd.ExcelFile(arquivo) as xls:
        estrutura = ler_estrutura(xls)
        alunos, inconsistencias = ler_alunos(xls)
    saida, totais, nao_alocados, status, objetivo = resolver(alunos, estrutura)
    for aluno in nao_alocados:
        inconsistencias.append({"Linha": aluno.linha, "Nome": aluno.nome,
                                "Motivo": f"Sem turma: não há vaga disponível no período {aluno.periodo.title()}."})
    linhas = [
        f"Status do solver: {status}",
        f"Valor da função objetivo: {objetivo}",
        f"Alunos alocados: {len(saida)} | Sem turma: {len(nao_alocados)}",
        "",
        "DISTRIBUIÇÃO (Nome | Sexo | Disponibilidade | Turma)",
        *[f"{r['Nome']} | {r['Sexo']} | {r['Disponibilidade']} | {r['Turma']}" for r in saida],
        "",
        "TOTAIS POR TURMA",
        *[f"{nome}: {quantidade}" for nome, quantidade in totais.items()],
    ]
    if nao_alocados:
        linhas.extend(["", "ALUNOS SEM TURMA", *[f"Linha {a.linha} | {a.nome} | {a.periodo.title()}" for a in nao_alocados]])
    if inconsistencias:
        linhas.extend(["", "INCONSISTÊNCIAS / AVISOS"])
        linhas.extend(f"Linha {r['Linha']} | {r['Nome']} | {r['Motivo']}" for r in inconsistencias)
    linhas.extend(["", "Modo de depuração: o arquivo Excel não foi alterado."])
    return "\n".join(linhas)


def interface() -> None:
    janela = tk.Tk()
    janela.title("Ensalamento — ABC Aprendiz")
    janela.geometry("490x220")
    janela.resizable(False, False)
    tk.Label(janela, text="Ensalamento ABC Aprendiz", font=("Segoe UI", 17, "bold")).pack(pady=(24, 8))
    tk.Label(janela, text="Escolha o arquivo Excel do cenário para gerar a distribuição.", font=("Segoe UI", 10)).pack(pady=4)
    status = tk.StringVar(value="Pronto para selecionar o arquivo.")
    tk.Label(janela, textvariable=status, wraplength=440, justify="center").pack(pady=12)
    botao = tk.Button(janela, text="Selecionar Excel e ensalar", font=("Segoe UI", 11, "bold"), padx=18, pady=9)

    def escolher() -> None:
        caminho = filedialog.askopenfilename(title="Selecione o cenário Excel", filetypes=[("Planilhas Excel", "*.xlsx")])
        if not caminho:
            return
        status.set("Resolvendo. A distribuição será impressa no terminal ao concluir.")
        botao.config(state="disabled")

        def trabalho() -> None:
            try:
                relatorio = executar(Path(caminho))
                print(relatorio, flush=True)
                janela.after(0, lambda: finalizado())
            except Exception as erro:
                print(f"Erro: {erro}", file=sys.stderr, flush=True)
                janela.after(0, lambda mensagem=str(erro): falhou(mensagem))

        threading.Thread(target=trabalho, daemon=True).start()

    def finalizado() -> None:
        botao.config(state="normal")
        status.set("Concluído. Veja a distribuição e os avisos no terminal.")
        messagebox.showinfo("Concluído", "A distribuição e os avisos foram impressos no terminal.")

    def falhou(mensagem: str) -> None:
        botao.config(state="normal")
        status.set("Falha ao gerar distribuição. Veja o terminal.")
        messagebox.showerror("Falha no ensalamento", mensagem)

    botao.config(command=escolher)
    botao.pack(pady=4)
    janela.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            print(executar(Path(sys.argv[1])))
        except Exception as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            raise SystemExit(1)
    else:
        interface()

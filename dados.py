"""Dados e nomenclatura compartilhados pelo solver e pela análise da solução."""
from __future__ import annotations

from dataclasses import dataclass


TURNOS = ("MANHÃ", "TARDE")
Turma = tuple[str, str, int]  # turno, nome, capacidade


@dataclass(frozen=True)
class Aluno:
    linha: int
    nome: str
    sexo: str
    periodo: str


def letras_turma(indice: int) -> str:
    """Converte um índice a partir de zero em A…Z, AA…AZ, BA…ZZ, AAA… .

    Usa a mesma sequência das colunas de uma planilha: cada posição tem
    letras de A a Z, sem um algarismo que represente zero.
    """
    if indice < 0:
        raise ValueError("O índice da turma não pode ser negativo.")
    numero = indice + 1
    letras = []
    while numero:
        numero, resto = divmod(numero - 1, 26)
        letras.append(chr(ord("A") + resto))
    return "".join(reversed(letras))


def criar_turmas(estrutura: dict[str, dict[str, int]]) -> list[Turma]:
    """Expõe todas as turmas, inclusive vazias, com a nomenclatura do modelo."""
    turmas = []
    for periodo in TURNOS:
        for _ in range(estrutura[periodo]["turmas"]):
            letra = letras_turma(len(turmas))
            turmas.append((periodo, f"{periodo} - {letra}", int(estrutura[periodo]["vagas"])))
    return turmas

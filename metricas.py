"""Métricas de gestão de uma solução pronta, sem solver, interface ou I/O."""
from __future__ import annotations

from collections import Counter

from dados import Aluno, TURNOS, criar_turmas


def _percentual(parte: int, total: int) -> float:
    return 100.0 * parte / total if total else 0.0


def _capacidade(capacidade: int, utilizados: int) -> dict:
    """Centraliza ocupação e ociosidade; sem capacidade ambas as taxas são zero."""
    livres = capacidade - utilizados
    return {
        "capacidade_total": capacidade,
        "vagas_utilizadas": utilizados,
        "vagas_ociosas": livres,
        "taxa_ocupacao": _percentual(utilizados, capacidade),
        "taxa_ociosidade": _percentual(livres, capacidade),
    }


def _arredondar(valor):
    if isinstance(valor, float):
        return round(valor, 2)
    if isinstance(valor, dict):
        return {chave: _arredondar(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [_arredondar(item) for item in valor]
    return valor


def calcular_metricas(
    alunos: list[Aluno],
    estrutura: dict[str, dict[str, int]],
    saida: list[dict],
    nao_alocados: list[Aluno],
    status_solver: str,
    valor_objetivo: float | None,
) -> dict:
    """Analisa a mesma instância e a saída de ``resolver``, sem otimizar novamente.

    ``saida`` contém somente alocados. Registros inválidos da entrada não entram
    em ``alunos``; homônimos são preservados como registros distintos. Os
    argumentos de status e objetivo são mantidos por compatibilidade com a
    integração; não integram as métricas de gestão retornadas.

    Percentuais usam a escala 0–100, com duas casas somente no retorno.
    Turmas vazias entram no mínimo, máximo e amplitude de seu próprio turno.
    Sem turmas, esses três valores são zero. A variação H/M é descritiva:
    mulheres menos homens, sem classificação de qualidade. Todos os empates
    na maior diferença absoluta são preservados, inclusive com sinais opostos.
    Entradas não são modificadas; inconsistências entre instância e solução
    geram ``ValueError``.
    """
    cadastro_turmas = criar_turmas(estrutura)
    por_nome = {nome: (turno, capacidade) for turno, nome, capacidade in cadastro_turmas}
    if any(capacidade < 0 for _, _, capacidade in cadastro_turmas):
        raise ValueError("A capacidade das turmas não pode ser negativa.")
    disponiveis = Counter((str(a.nome), str(a.sexo), str(a.periodo)) for a in alunos)
    sem_turma = Counter((str(a.nome), str(a.sexo), str(a.periodo)) for a in nao_alocados)
    alocados = Counter()
    sexos_turmas = {nome: Counter() for nome in por_nome}
    for registro in saida:
        nome_turma = str(registro["Turma"])
        turno = str(registro["Disponibilidade"]).strip().upper()
        sexo = str(registro["Sexo"])
        if nome_turma not in por_nome or por_nome[nome_turma][0] != turno:
            raise ValueError("Turma inexistente ou incompatível com a disponibilidade do aluno.")
        alocados[str(registro["Nome"]), sexo, turno] += 1
        sexos_turmas[nome_turma][sexo] += 1
    if disponiveis != alocados + sem_turma:
        raise ValueError("Alocados e não alocados devem corresponder aos alunos válidos da instância.")
    if any(turno not in TURNOS for _, _, turno in disponiveis):
        raise ValueError("Disponibilidade fora dos turnos da instância.")

    turmas = []
    for turno, nome, capacidade in cadastro_turmas:
        sexos = sexos_turmas[nome]
        quantidade = sum(sexos.values())  # Inclui eventuais categorias futuras além de F/M.
        if quantidade > capacidade:
            raise ValueError(f"A turma '{nome}' excede a capacidade.")
        mulheres, homens = int(sexos["F"]), int(sexos["M"])
        turmas.append({
            "nome": nome,
            "turno": turno,
            "capacidade": capacidade,
            "total_alunos": quantidade,
            "mulheres": mulheres,
            "homens": homens,
            "diferenca_genero": mulheres - homens,
            "vagas_ociosas": capacidade - quantidade,
            "taxa_ocupacao": _percentual(quantidade, capacidade),
            "lotada": quantidade == capacidade,
            "vazia": quantidade == 0,
        })

    por_turno = {}
    balanceamento = {}
    for turno in TURNOS:
        turmas_turno = [t for t in turmas if t["turno"] == turno]
        tamanhos = [t["total_alunos"] for t in turmas_turno]
        minimo, maximo = min(tamanhos, default=0), max(tamanhos, default=0)
        por_turno[turno] = {
            "alunos_disponiveis": sum(a.periodo == turno for a in alunos),
            "alunos_alocados": sum(tamanhos),
            "alunos_sem_turma": sum(a.periodo == turno for a in nao_alocados),
            "total_turmas": len(turmas_turno),
            **_capacidade(sum(t["capacidade"] for t in turmas_turno), sum(tamanhos)),
        }
        balanceamento[turno] = {
            "alunos": {"minimo": minimo, "maximo": maximo, "amplitude": maximo - minimo},
        }

    maior_variacao = max((abs(t["diferenca_genero"]) for t in turmas), default=0)
    empatadas = [t for t in turmas if abs(t["diferenca_genero"]) == maior_variacao]
    predominancias = []
    if any(t["diferenca_genero"] > 0 for t in empatadas):
        predominancias.append("mulheres")
    if any(t["diferenca_genero"] < 0 for t in empatadas):
        predominancias.append("homens")
    if empatadas and maior_variacao == 0:
        predominancias.append("equilibrado")

    return _arredondar({
        "resumo": {
            "total_alunos": len(alunos),
            "alunos_alocados": len(saida),
            "alunos_sem_turma": len(nao_alocados),
            "percentual_alocados": _percentual(len(saida), len(alunos)),
            "total_turmas": len(turmas),
            **_capacidade(sum(t["capacidade"] for t in turmas), len(saida)),
        },
        "por_turno": por_turno,
        "turmas": turmas,
        "nao_alocados": {
            "total": len(nao_alocados),
            "por_turno": {turno: por_turno[turno]["alunos_sem_turma"] for turno in TURNOS},
            "alunos": [
                {"nome": str(a.nome), "sexo": str(a.sexo), "disponibilidade": str(a.periodo)}
                for a in nao_alocados
            ],
        },
        "balanceamento": balanceamento,
        "destaques": {
            "variacao_genero": {
                "quantidade": maior_variacao,
                "predominancias": predominancias,
                "turmas": [t["nome"] for t in empatadas],
            },
        },
    })

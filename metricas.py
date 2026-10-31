"""Análise de uma solução já calculada, sem solver, interface ou efeitos de I/O."""
from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import fmean, pstdev

from dados import Aluno, TURNOS, criar_turmas


def _percentual(parte: int, total: int) -> float:
    return 100.0 * parte / total if total else 0.0


def _generos(contagens: Counter[str]) -> dict:
    """Mantém os campos F/M e preserva outras categorias no detalhamento."""
    return {
        "mulheres": int(contagens["F"]),
        "homens": int(contagens["M"]),
        "por_sexo": {str(sexo): int(total) for sexo, total in sorted(contagens.items())},
    }


def _dispersao(valores: list[int], referencia: float) -> dict:
    """Desvio padrão populacional: as turmas são a população inteira do turno.

    A dispersão observada usa a média dos alocados. A referência do modelo usa
    todos os alunos válidos disponíveis, inclusive os que ficaram sem vaga.
    Sem turmas, ambas as médias de referência são convencionadas como zero.
    """
    media = fmean(valores) if valores else 0.0
    minimo = min(valores, default=0)
    maximo = max(valores, default=0)
    return {
        "media": media,
        "minimo": minimo,
        "maximo": maximo,
        "amplitude": maximo - minimo,
        "desvio_padrao": pstdev(valores) if valores else 0.0,
        "soma_desvios_absolutos": sum((abs(v - media) for v in valores), 0.0),
        "media_referencia_modelo": referencia,
        "soma_desvios_referencia_modelo": sum((abs(v - referencia) for v in valores), 0.0),
    }


def _extremo(turmas: list[dict], campo: str, maior: bool) -> dict:
    """Retorna todos os empates usando valores ainda não arredondados."""
    if not turmas:
        return {"valor": None, "turmas": []}
    valor = (max if maior else min)(t[campo] for t in turmas)
    return {"valor": valor, "turmas": [t["nome"] for t in turmas if t[campo] == valor]}


def _arredondar(valor):
    """Arredonda somente a estrutura final; os cálculos mantêm a precisão."""
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
    """Analisa a instância válida e a saída de ``resolver`` sem otimizar novamente.

    ``alunos`` e ``estrutura`` são os mesmos dados entregues ao solver. Os demais
    argumentos vêm de seu retorno; ``totais`` é dispensável, pois a distribuição
    é contada diretamente em ``saida``. Entradas e solução não são modificadas.
    Incompatibilidades entre instância e solução geram ``ValueError``.

    Percentuais estão na escala 0–100, diferenças de proporções em pontos
    percentuais. Divisões por zero e dispersões sem turmas retornam zero;
    destaques sem candidatas retornam ``valor=None`` e uma lista vazia.

    Turmas vazias entram na dispersão de quantidades, mas são excluídas das
    comparações de proporções de gênero, pois não possuem uma proporção definida.
    Seus campos percentuais individuais usam zero por convenção.
    """
    objetivo = None if valor_objetivo is None else float(valor_objetivo)
    if objetivo is not None and not isfinite(objetivo):
        raise ValueError("O valor objetivo precisa ser finito ou None.")

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
    # Contar registros, sem usar o nome como identificador único, preserva homônimos.
    if disponiveis != alocados + sem_turma:
        raise ValueError("Alocados e não alocados devem corresponder aos alunos válidos da instância.")
    if any(turno not in TURNOS for _, _, turno in disponiveis):
        raise ValueError("Disponibilidade fora dos turnos da instância.")

    turmas = []
    for turno, nome, capacidade in cadastro_turmas:
        sexos = sexos_turmas[nome]
        quantidade = sum(sexos.values())
        if quantidade > capacidade:
            raise ValueError(f"A turma '{nome}' excede a capacidade.")
        turmas.append({
            "nome": nome,
            "turno": turno,
            "capacidade": capacidade,
            "total_alunos": quantidade,
            **_generos(sexos),
            "percentual_mulheres": _percentual(sexos["F"], quantidade),
            "percentual_homens": _percentual(sexos["M"], quantidade),
            "vagas_ociosas": capacidade - quantidade,
            "taxa_ocupacao": _percentual(quantidade, capacidade),
            "lotada": quantidade == capacidade,
            "vazia": quantidade == 0,
        })

    por_turno = {}
    balanceamento = {}
    for turno in TURNOS:
        turmas_turno = [t for t in turmas if t["turno"] == turno]
        alunos_turno = [a for a in alunos if a.periodo == turno]
        sem_turma_turno = [a for a in nao_alocados if a.periodo == turno]
        sexos_disponiveis = Counter(str(a.sexo) for a in alunos_turno)
        sexos_sem_turma = Counter(str(a.sexo) for a in sem_turma_turno)
        sexos_alocados = Counter()
        for turma in turmas_turno:
            sexos_alocados.update(sexos_turmas[turma["nome"]])
        utilizados = sum(t["total_alunos"] for t in turmas_turno)
        capacidade = sum(t["capacidade"] for t in turmas_turno)
        por_turno[turno] = {
            "alunos_disponiveis": len(alunos_turno),
            "alunos_alocados": utilizados,
            "alunos_sem_turma": len(sem_turma_turno),
            "total_turmas": len(turmas_turno),
            "capacidade_total": capacidade,
            "vagas_utilizadas": utilizados,
            "vagas_ociosas": capacidade - utilizados,
            "taxa_ocupacao": _percentual(utilizados, capacidade),
            "mulheres_alocadas": int(sexos_alocados["F"]),
            "homens_alocados": int(sexos_alocados["M"]),
            "mulheres_sem_turma": int(sexos_sem_turma["F"]),
            "homens_sem_turma": int(sexos_sem_turma["M"]),
            "por_sexo": {
                "disponiveis": _generos(sexos_disponiveis)["por_sexo"],
                "alocados": _generos(sexos_alocados)["por_sexo"],
                "sem_turma": _generos(sexos_sem_turma)["por_sexo"],
            },
        }
        numero_turmas = len(turmas_turno)
        proporcao_global = _percentual(sexos_disponiveis["F"], len(alunos_turno))
        com_alunos = [t for t in turmas_turno if not t["vazia"]]
        balanceamento[turno] = {
            "alunos": _dispersao(
                [t["total_alunos"] for t in turmas_turno],
                len(alunos_turno) / numero_turmas if numero_turmas else 0.0,
            ),
            "genero": {
                **_dispersao(
                    [t["mulheres"] for t in turmas_turno],
                    sexos_disponiveis["F"] / numero_turmas if numero_turmas else 0.0,
                ),
                "percentual_mulheres_turno": proporcao_global,
                "percentual_mulheres_alocadas": _percentual(sexos_alocados["F"], utilizados),
                "percentual_mulheres_por_turma": {
                    t["nome"]: t["percentual_mulheres"] for t in turmas_turno
                },
                "maior_diferenca_percentual": max(
                    (abs(t["percentual_mulheres"] - proporcao_global) for t in com_alunos),
                    default=0.0,
                ),
            },
        }

    quantidade_alocada = len(saida)
    capacidade_total = sum(t["capacidade"] for t in turmas)
    media = quantidade_alocada / len(turmas) if turmas else 0.0
    com_alunos = [t for t in turmas if not t["vazia"]]
    proporcoes = [t["percentual_mulheres"] for t in com_alunos]
    maior_turma = _extremo(turmas, "total_alunos", True)
    menor_turma = _extremo(turmas, "total_alunos", False)
    resultado = {
        "resumo": {
            "total_alunos": len(alunos),
            "alunos_alocados": quantidade_alocada,
            "alunos_sem_turma": len(nao_alocados),
            "percentual_alocados": _percentual(quantidade_alocada, len(alunos)),
            "percentual_sem_turma": _percentual(len(nao_alocados), len(alunos)),
            "total_turmas": len(turmas),
            "capacidade_total": capacidade_total,
            "vagas_utilizadas": quantidade_alocada,
            "vagas_ociosas": capacidade_total - quantidade_alocada,
            "taxa_ocupacao": _percentual(quantidade_alocada, capacidade_total),
            "status_solver": str(status_solver),
            "valor_objetivo": objetivo,
        },
        "por_turno": por_turno,
        "turmas": turmas,
        "situacao_turmas": {
            "turmas_lotadas": [t["nome"] for t in turmas if t["lotada"]],
            "turmas_nao_lotadas": [t["nome"] for t in turmas if t["total_alunos"] < t["capacidade"]],
            "turmas_vazias": [t["nome"] for t in turmas if t["vazia"]],
        },
        "nao_alocados": {
            "total": len(nao_alocados),
            **_generos(Counter(str(a.sexo) for a in nao_alocados)),
            "por_turno": {turno: por_turno[turno]["alunos_sem_turma"] for turno in TURNOS},
            "alunos": [
                {"nome": str(a.nome), "sexo": str(a.sexo), "disponibilidade": str(a.periodo)}
                for a in nao_alocados
            ],
        },
        "balanceamento": balanceamento,
        "destaques": {
            "capacidade": {
                "maior_ocupacao": _extremo(turmas, "taxa_ocupacao", True),
                "menor_ocupacao": _extremo(turmas, "taxa_ocupacao", False),
                "mais_vagas_ociosas": _extremo(turmas, "vagas_ociosas", True),
                "turmas_100_porcento": sum(t["lotada"] for t in turmas),
                "turmas_abaixo_50_porcento": sum(
                    t["capacidade"] > 0 and t["taxa_ocupacao"] < 50 for t in turmas
                ),
            },
            "distribuicao": {
                "media_alunos": media,
                "maior_turma": maior_turma,
                "menor_turma": menor_turma,
                "amplitude": (maior_turma["valor"] - menor_turma["valor"]) if turmas else 0,
                "turmas_acima_media": [t["nome"] for t in turmas if t["total_alunos"] > media],
                "turmas_abaixo_media": [t["nome"] for t in turmas if t["total_alunos"] < media],
            },
            "genero": {
                "maior_percentual_mulheres": _extremo(com_alunos, "percentual_mulheres", True),
                "menor_percentual_mulheres": _extremo(com_alunos, "percentual_mulheres", False),
                "diferenca_maxima_percentual": max(proporcoes) - min(proporcoes) if proporcoes else 0.0,
            },
        },
    }
    return _arredondar(resultado)

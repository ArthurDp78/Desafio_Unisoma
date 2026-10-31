"""Métricas úteis ao painel de gestão, sem executar o solver."""
from copy import deepcopy
import json
import unittest

from apresentacao import texto_diferenca_turmas, texto_variacao_genero
from dados import Aluno, criar_turmas
from metricas import calcular_metricas


def analisar(sexos_por_turma, estrutura=None, sem_turma=()):
    estrutura = estrutura or {
        "MANHÃ": {"turmas": 2, "vagas": 5}, "TARDE": {"turmas": 2, "vagas": 4},
    }
    alunos, saida = [], []
    for (turno, nome, _), sexos in zip(criar_turmas(estrutura), sexos_por_turma):
        for sexo in sexos:
            aluno = Aluno(len(alunos) + 2, f"Aluno {len(alunos)}", sexo, turno)
            alunos.append(aluno)
            saida.append({"Nome": aluno.nome, "Sexo": sexo, "Disponibilidade": turno.title(), "Turma": nome})
    nao_alocados = []
    for sexo, turno in sem_turma:
        aluno = Aluno(len(alunos) + 2, f"Aluno {len(alunos)}", sexo, turno)
        alunos.append(aluno)
        nao_alocados.append(aluno)
    antes = deepcopy((alunos, estrutura, saida, nao_alocados))
    metricas = calcular_metricas(alunos, estrutura, saida, nao_alocados, "Optimal", None)
    assert antes == (alunos, estrutura, saida, nao_alocados)
    return metricas


class MetricasTest(unittest.TestCase):
    def setUp(self):
        self.metricas = analisar(("FFFM", "FM", "MMM", "F"), sem_turma=(("F", "MANHÃ"), ("M", "TARDE")))

    def test_resumo_ocupacao_ociosidade_e_invariantes(self):
        resumo = self.metricas["resumo"]
        self.assertEqual(resumo, {
            "total_alunos": 12, "alunos_alocados": 10, "alunos_sem_turma": 2,
            "percentual_alocados": 83.33, "total_turmas": 4,
            "capacidade_total": 18, "vagas_utilizadas": 10, "vagas_ociosas": 8,
            "taxa_ocupacao": 55.56, "taxa_ociosidade": 44.44,
        })
        self.assertAlmostEqual(resumo["taxa_ocupacao"] + resumo["taxa_ociosidade"], 100, delta=0.01)
        self.assertEqual(resumo["alunos_alocados"] + resumo["alunos_sem_turma"], resumo["total_alunos"])
        self.assertEqual(sum(t["total_alunos"] for t in self.metricas["turmas"]), resumo["alunos_alocados"])
        for turma in self.metricas["turmas"]:
            self.assertEqual(turma["mulheres"] + turma["homens"], turma["total_alunos"])
            self.assertLessEqual(turma["total_alunos"], turma["capacidade"])
        self.assertEqual(self.metricas, json.loads(json.dumps(self.metricas, ensure_ascii=False, allow_nan=False)))

    def test_turnos_e_amplitudes_separadas(self):
        manha, tarde = self.metricas["por_turno"]["MANHÃ"], self.metricas["por_turno"]["TARDE"]
        for dados, disponiveis, alocados, capacidade, ocupacao in (
            (manha, 7, 6, 10, 60.0), (tarde, 5, 4, 8, 50.0),
        ):
            self.assertEqual(dados["alunos_disponiveis"], disponiveis)
            self.assertEqual(dados["alunos_alocados"], alocados)
            self.assertEqual(dados["alunos_sem_turma"], 1)
            self.assertEqual(dados["capacidade_total"], capacidade)
            self.assertEqual(dados["taxa_ocupacao"], ocupacao)
            self.assertEqual(dados["vagas_ociosas"], capacidade - alocados)
            self.assertAlmostEqual(dados["taxa_ocupacao"] + dados["taxa_ociosidade"], 100, delta=0.01)
        for chave in ("alunos_alocados", "alunos_sem_turma", "total_turmas", "capacidade_total", "vagas_utilizadas", "vagas_ociosas"):
            self.assertEqual(manha[chave] + tarde[chave], self.metricas["resumo"][chave])
        self.assertEqual(self.metricas["balanceamento"], {
            "MANHÃ": {"alunos": {"minimo": 2, "maximo": 4, "amplitude": 2}},
            "TARDE": {"alunos": {"minimo": 1, "maximo": 3, "amplitude": 2}},
        })

    def test_maior_variacao_homens(self):
        variacao = self.metricas["destaques"]["variacao_genero"]
        self.assertEqual(variacao, {"quantidade": 3, "predominancias": ["homens"], "turmas": ["TARDE - C"]})
        self.assertEqual(self.metricas["turmas"][2]["diferenca_genero"], -3)
        self.assertEqual(texto_variacao_genero(variacao), "3 homens a mais")

    def test_variacao_mulheres_equilibrio_e_empates(self):
        for sexos, quantidade, predominancias, texto in (
            (("FFF", "M", "", ""), 3, ["mulheres"], "3 mulheres a mais"),
            (("F", "", "", ""), 1, ["mulheres"], "1 mulher a mais"),
            (("FM", "FM", "", ""), 0, ["equilibrado"], "Equilibrado"),
            (("FFF", "MMM", "", ""), 3, ["mulheres", "homens"], "3 mulheres a mais · 3 homens a mais"),
        ):
            with self.subTest(sexos=sexos):
                variacao = analisar(sexos)["destaques"]["variacao_genero"]
                self.assertEqual(variacao["quantidade"], quantidade)
                self.assertEqual(variacao["predominancias"], predominancias)
                self.assertEqual(texto_variacao_genero(variacao), texto)
        empate = analisar(("FFF", "MMM", "", ""))["destaques"]["variacao_genero"]
        self.assertEqual(empate["turmas"], ["MANHÃ - A", "MANHÃ - B"])

    def test_textos_de_tamanho(self):
        self.assertEqual(texto_diferenca_turmas(0), "turmas com o mesmo tamanho")
        self.assertEqual(texto_diferenca_turmas(1), "até 1 aluno")
        self.assertEqual(texto_diferenca_turmas(2), "até 2 alunos")

    def test_nao_alocados_preservados(self):
        dados = self.metricas["nao_alocados"]
        self.assertEqual(dados["total"], 2)
        self.assertEqual(dados["por_turno"], {"MANHÃ": 1, "TARDE": 1})
        self.assertEqual(len(dados["alunos"]), 2)
        self.assertEqual(set(dados["alunos"][0]), {"nome", "sexo", "disponibilidade"})

    def test_turnos_vazios_sem_turmas_e_sem_capacidade(self):
        for numero_turmas, vagas in ((0, 0), (2, 0), (2, 3)):
            with self.subTest(turmas=numero_turmas, vagas=vagas):
                estrutura = {p: {"turmas": numero_turmas, "vagas": vagas} for p in ("MANHÃ", "TARDE")}
                dados = analisar((), estrutura)
                self.assertEqual(dados["resumo"]["taxa_ocupacao"], 0.0)
                self.assertEqual(dados["resumo"]["taxa_ociosidade"], 100.0 if numero_turmas and vagas else 0.0)
                self.assertEqual(dados["balanceamento"]["MANHÃ"]["alunos"]["amplitude"], 0)
                json.dumps(dados, allow_nan=False)
        estrutura = {"MANHÃ": {"turmas": 0, "vagas": 0}, "TARDE": {"turmas": 1, "vagas": 3}}
        dados = analisar(("",), estrutura, sem_turma=(("F", "MANHÃ"),))
        self.assertEqual(dados["por_turno"]["MANHÃ"]["alunos_sem_turma"], 1)
        self.assertEqual(dados["por_turno"]["TARDE"]["taxa_ociosidade"], 100.0)

    def test_mantem_contagem_de_categorias_futuras(self):
        dados = analisar(("FX", "", "", ""))
        self.assertEqual(dados["resumo"]["alunos_alocados"], 2)
        self.assertEqual(dados["turmas"][0]["total_alunos"], 2)


if __name__ == "__main__":
    unittest.main()

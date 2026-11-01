"""Verifica as transições alfabéticas e a integração com solver e exportação."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook, load_workbook

from apresentacao import processar_planilha
from dados import criar_turmas, letras_turma
from ensalamento import ler_alunos, ler_estrutura
from metricas import calcular_metricas
import pandas as pd


class NomesTurmasTest(unittest.TestCase):
    def test_transicoes_alfabeticas(self):
        esperados = {
            0: "A", 25: "Z", 26: "AA", 27: "AB", 51: "AZ",
            52: "BA", 701: "ZZ", 702: "AAA", 703: "AAB",
        }
        for indice, nome in esperados.items():
            with self.subTest(indice=indice):
                self.assertEqual(letras_turma(indice), nome)
        with self.assertRaises(ValueError):
            letras_turma(-1)

    def test_sequencia_continua_entre_turnos(self):
        estrutura = {"MANHÃ": {"turmas": 26, "vagas": 30}, "TARDE": {"turmas": 28, "vagas": 20}}
        turmas = criar_turmas(estrutura)
        self.assertEqual(turmas[25], ("MANHÃ", "MANHÃ - Z", 30))
        self.assertEqual(turmas[26], ("TARDE", "TARDE - AA", 20))
        self.assertEqual(turmas[51], ("TARDE", "TARDE - AZ", 20))
        self.assertEqual(turmas[52], ("TARDE", "TARDE - BA", 20))
        self.assertEqual(len({nome for _, nome, _ in turmas}), 54)

    def test_solver_planilha_apresentacao_e_metricas_com_29_turmas(self):
        with TemporaryDirectory() as pasta:
            origem = Path(pasta) / "entrada.xlsx"
            livro = Workbook()
            alunos_ws = livro.active
            alunos_ws.title = "Alunos"
            alunos_ws.append(["Nome", "Sexo", "Disponibilidade"])
            for indice in range(27):
                alunos_ws.append([f"Aluna {indice}", "F", "Manhã"])
            alunos_ws.append(["Aluno da tarde", "M", "Tarde"])
            turmas_ws = livro.create_sheet("Turmas")
            turmas_ws.append(["Recursos", "Quantidade"])
            for registro in (("turmas_manha", 27), ("turmas_tarde", 2), ("vagas_manha", 1), ("vagas_tarde", 1)):
                turmas_ws.append(registro)
            livro.save(origem)
            livro.close()
            antes = origem.read_bytes()

            resultado = processar_planilha(origem)
            self.assertEqual(origem.read_bytes(), antes)
            nomes = list(resultado.grupos)
            self.assertEqual(len(nomes), 29)
            self.assertEqual(nomes[25:], ["MANHÃ - Z", "MANHÃ - AA", "TARDE - AB", "TARDE - AC"])
            self.assertEqual(len(resultado.distribuicao), 28)
            self.assertEqual(resultado.totais["MANHÃ - AA"], 1)

            exportado = load_workbook(BytesIO(resultado.planilha))
            try:
                nomes_exportados = {r[3] for r in exportado["Ensalamento"].iter_rows(min_row=2, values_only=True)}
                self.assertIn("MANHÃ - AA", nomes_exportados)
                self.assertTrue(nomes_exportados.issubset(resultado.grupos))
            finally:
                exportado.close()

            with pd.ExcelFile(origem) as excel:
                alunos, _ = ler_alunos(excel)
                estrutura = ler_estrutura(excel)
            metricas = calcular_metricas(alunos, estrutura, resultado.distribuicao, [], "Optimal", None)
            self.assertEqual([t["nome"] for t in metricas["turmas"]], nomes)
            self.assertEqual(metricas["resumo"]["alunos_alocados"], 28)


if __name__ == "__main__":
    unittest.main()

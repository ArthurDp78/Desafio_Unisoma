"""Integração da UI desktop, cópia de trabalho e exportação sem recálculo."""
from collections import Counter
from dataclasses import replace
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation, QTimer, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from apresentacao import ResultadoInterface, exportar_planilha, processar_planilha
import ensalamento
from dados import Aluno
from interface_desktop import (
    Grafico, JanelaPrincipal, LARGURA_CARDS_TRES_COLUNAS,
    LARGURA_DASHBOARD_DESKTOP,
)
from metricas import calcular_metricas


def criar_entrada(caminho):
    livro = Workbook()
    alunos = livro.active
    alunos.title = "Alunos"
    alunos.append(["Nome", "Sexo", "Disponibilidade"])
    for linha in [["Ana", "F", "Manhã"], ["Ana", "F", "Manhã"], ["João", "M", "Tarde"],
                  ["Clara", "F", "Tarde"], ["Paulo", "X", "Noite"]]:
        alunos.append(linha)
    turmas = livro.create_sheet("Turmas")
    turmas.append(["Recursos", "Quantidade"])
    for linha in [["turmas_manha", 2], ["turmas_tarde", 1], ["vagas_manha", 2], ["vagas_tarde", 2]]:
        turmas.append(linha)
    notas = livro.create_sheet("Notas")
    notas["A1"] = "Preservar aba adicional"
    livro.create_sheet("Ensalamento")["H30"] = "Nota à direita da tabela de saída"
    livro.create_sheet("Inconsistências")["G28"] = "Nota à direita dos avisos"
    alunos["A1"].font = Font(bold=True)
    livro.save(caminho)
    livro.close()


def criar_entrada_sem_vagas(caminho):
    """415 alunos válidos e capacidade para 403, usando o solver real."""
    criar_entrada(caminho)
    livro = load_workbook(caminho)
    alunos = livro["Alunos"]
    alunos.delete_rows(2, alunos.max_row - 1)
    for indice in range(215):
        alunos.append([f"Aluna manhã {indice}", "F", "Manhã"])
    for indice in range(200):
        alunos.append([f"Aluno tarde {indice}", "M", "Tarde"])
    turmas = livro["Turmas"]
    turmas.delete_rows(2, turmas.max_row - 1)
    for linha in [["turmas_manha", 1], ["turmas_tarde", 1], ["vagas_manha", 203], ["vagas_tarde", 200]]:
        turmas.append(linha)
    livro.save(caminho)
    livro.close()


class PlanilhaTest(unittest.TestCase):
    def _processar_verificando_metricas(self, origem):
        with (
            patch("ensalamento.resolver", wraps=ensalamento.resolver) as resolver,
            patch("ensalamento.salvar_resultado_excel", wraps=ensalamento.salvar_resultado_excel) as salvar,
            patch("apresentacao.calcular_metricas", wraps=calcular_metricas) as calcular,
        ):
            resultado = processar_planilha(origem)
        resolver.assert_called_once()
        salvar.assert_called_once()
        calcular.assert_called_once()
        argumentos = calcular.call_args.kwargs
        # As métricas recebem os próprios objetos usados na resolução e na
        # gravação da cópia, em vez de uma reconstrução da planilha de saída.
        self.assertIs(argumentos["alunos"], resolver.call_args.args[0])
        self.assertIs(argumentos["estrutura"], resolver.call_args.args[1])
        self.assertIs(argumentos["saida"], salvar.call_args.args[1])
        self.assertIs(argumentos["nao_alocados"], salvar.call_args.kwargs["nao_alocados"])
        self.assertNotEqual(Path(salvar.call_args.args[0]), origem.resolve())
        self.assertIsInstance(resultado.metricas, dict)
        self.assertTrue({"resumo", "por_turno", "turmas", "nao_alocados",
                         "balanceamento", "destaques"}.issubset(resultado.metricas))
        resumo = resultado.metricas["resumo"]
        self.assertEqual(resumo["alunos_alocados"], len(resultado.distribuicao))
        self.assertEqual(resumo["alunos_sem_turma"], resultado.sem_turma)
        self.assertEqual(resumo["total_turmas"], len(resultado.grupos))
        if resumo["capacidade_total"]:
            self.assertAlmostEqual(resumo["taxa_ocupacao"] + resumo["taxa_ociosidade"], 100, delta=0.01)
        self.assertEqual(resultado.metricas, json.loads(json.dumps(resultado.metricas, allow_nan=False)))
        return resultado

    def test_modelo_original_roda_em_copia_e_exportacao_preserva_abas(self):
        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta) / "entrada.xlsx"
            criar_entrada(origem)
            antes = origem.read_bytes()
            resultado = self._processar_verificando_metricas(origem)
            self.assertEqual(origem.read_bytes(), antes)
            self.assertEqual(len(resultado.distribuicao), 4)
            self.assertEqual(resultado.sem_turma, 0)
            self.assertEqual(resultado.metricas["resumo"]["total_alunos"], 4)
            self.assertEqual(resultado.metricas["resumo"]["taxa_ocupacao"], 66.67)
            self.assertEqual(resultado.metricas["resumo"]["taxa_ociosidade"], 33.33)
            self.assertEqual(resultado.metricas["resumo"]["vagas_ociosas"], 2)
            self.assertEqual(len(resultado.grupos), 3)
            self.assertEqual(sum(resultado.totais.values()), 4)
            self.assertEqual(sum(sum(v) for v in resultado.sexos.values()), 4)
            self.assertEqual(sum(r["Nome"] == "Ana" for r in resultado.distribuicao), 2)
            self.assertIn("DADOS AUSENTES OU INVÁLIDOS", resultado.relatorio())
            self.assertIn("NOMES DUPLICADOS", resultado.relatorio())
            self.assertIn("Linha(s) 6", resultado.relatorio())
            destino = Path(pasta) / "saida.xlsx"
            with patch("ensalamento.resolver", side_effect=AssertionError("Não recalcular na exportação")):
                exportar_planilha(resultado, destino)
            self.assertEqual(destino.read_bytes(), resultado.planilha)
            livro = load_workbook(destino)
            self.assertEqual(livro.sheetnames, ["Alunos", "Turmas", "Notas", "Ensalamento", "Inconsistências"])
            self.assertEqual(livro["Notas"]["A1"].value, "Preservar aba adicional")
            self.assertEqual(livro["Alunos"]["A1"].font.bold, True)
            self.assertEqual(livro["Alunos"].max_row, 6)
            self.assertEqual(sum(c[0].value is not None for c in livro["Ensalamento"].iter_rows(min_row=2, max_col=1)), 4)
            self.assertEqual(livro["Ensalamento"]["H30"].value, "Nota à direita da tabela de saída")
            self.assertEqual(livro["Inconsistências"]["G28"].value, "Nota à direita dos avisos")
            self.assertEqual([c.value for c in livro["Inconsistências"][1]][:3], ["Linha", "Nome", "Motivo"])
            livro.close()
            self.assertEqual(origem.read_bytes(), antes)

    def test_falta_de_vagas_separa_alocados_e_exporta_resultado_completo(self):
        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta) / "entrada.xlsx"
            criar_entrada_sem_vagas(origem)
            antes = origem.read_bytes()
            resultado = self._processar_verificando_metricas(origem)
            self.assertEqual(origem.read_bytes(), antes)
            self.assertEqual(len(resultado.distribuicao), 403)
            self.assertEqual(resultado.sem_turma, 12)
            self.assertEqual(resultado.metricas["resumo"]["total_alunos"], 415)
            self.assertEqual(resultado.metricas["resumo"]["taxa_ocupacao"], 100.0)
            self.assertEqual(resultado.metricas["resumo"]["taxa_ociosidade"], 0.0)
            self.assertEqual(resultado.metricas["nao_alocados"]["total"], 12)
            self.assertEqual(len(resultado.grupos), 2)
            self.assertNotIn("SEM TURMA", resultado.grupos)
            self.assertTrue(all(r["Turma"] in resultado.grupos for r in resultado.distribuicao))
            self.assertEqual(sum(resultado.totais.values()), 403)
            self.assertEqual(sum(sum(v) for v in resultado.sexos.values()), 403)
            self.assertEqual(sorted(resultado.totais.values()), [200, 203])
            self.assertEqual(len(resultado.inconsistencias), 12)
            self.assertTrue(all("Aluno sem turma" in r["Motivo"] for r in resultado.inconsistencias))
            self.assertIn("ALUNOS SEM TURMA (12)", resultado.relatorio())

            destino = Path(pasta) / "saida.xlsx"
            with patch("ensalamento.resolver", side_effect=AssertionError("Não recalcular na exportação")):
                exportar_planilha(resultado, destino)
            self.assertEqual(destino.read_bytes(), resultado.planilha)
            self.assertEqual(origem.read_bytes(), antes)
            livro = load_workbook(destino)
            try:
                linhas = [r for r in livro["Ensalamento"].iter_rows(min_row=2, max_col=4, values_only=True) if r[0]]
                self.assertEqual(len(linhas), 415)
                sem_turma = [r for r in linhas if r[3] == "SEM TURMA"]
                self.assertEqual(len(sem_turma), 12)
                avisos = [r for r in livro["Inconsistências"].iter_rows(min_row=2, max_col=3, values_only=True) if r[0]]
                self.assertEqual(len(avisos), 12)
                self.assertEqual(Counter(r[0] for r in sem_turma), Counter(r[1] for r in avisos))
                self.assertEqual(livro["Alunos"].max_row, 416)
                self.assertEqual(livro["Notas"]["A1"].value, "Preservar aba adicional")
                self.assertEqual(livro["Ensalamento"]["H30"].value, "Nota à direita da tabela de saída")
            finally:
                livro.close()

    def test_falha_do_modelo_preserva_original_e_nao_oferece_resultado(self):
        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta) / "entrada.xlsx"
            criar_entrada(origem)
            antes = origem.read_bytes()
            with patch("ensalamento.executar_com_resultado", side_effect=ValueError("Solução não ótima")):
                with self.assertRaisesRegex(ValueError, "não ótima"):
                    processar_planilha(origem)
            self.assertEqual(origem.read_bytes(), antes)

    def test_executar_preserva_resumo_e_gravacao_no_proprio_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta) / "entrada.xlsx"
            criar_entrada(origem)
            antes = origem.read_bytes()
            with (
                patch("ensalamento.resolver", wraps=ensalamento.resolver) as resolver,
                patch("apresentacao.calcular_metricas", side_effect=AssertionError("Métricas são da apresentação")),
            ):
                resumo = ensalamento.executar(origem)
            resolver.assert_called_once()
            self.assertEqual(resumo, (
                "Ensalamento concluído e salvo no Excel.\n"
                "Alunos alocados: 4 | Sem turma: 0\n"
                "Inconsistências/avisos registrados: 2."
            ))
            self.assertNotEqual(origem.read_bytes(), antes)
            livro = load_workbook(origem)
            try:
                self.assertEqual(livro["Ensalamento"]["A2"].value, "Ana")
                self.assertEqual(livro["Inconsistências"]["A2"].value, 6)
                self.assertEqual(livro["Alunos"].max_row, 6)
            finally:
                livro.close()

    def test_exportacao_bloqueada_preserva_destino_e_limpa_temporario(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "saida.xlsx"
            destino.write_bytes(b"original")
            resultado = amostra()
            with patch("apresentacao.os.replace", side_effect=PermissionError):
                with self.assertRaisesRegex(PermissionError, "Feche a planilha"):
                    exportar_planilha(resultado, destino)
            self.assertEqual(destino.read_bytes(), b"original")
            self.assertEqual(list(Path(pasta).glob("abc_export_*")), [])


def amostra():
    grupos = {
        "MANHÃ - A": [{"Nome": "Ágata", "Sexo": "F", "Disponibilidade": "Manhã", "Turma": "MANHÃ - A"},
                      {"Nome": "João", "Sexo": "M", "Disponibilidade": "Manhã", "Turma": "MANHÃ - A"}],
        "MANHÃ - B": [],
        "TARDE - C": [{"Nome": "João", "Sexo": "M", "Disponibilidade": "Tarde", "Turma": "TARDE - C"}],
    }
    distribuicao = [r for g in grupos.values() for r in g]
    alunos = [Aluno(i + 2, r["Nome"], r["Sexo"], r["Disponibilidade"].upper())
              for i, r in enumerate(distribuicao)]
    estrutura = {"MANHÃ": {"turmas": 2, "vagas": 2}, "TARDE": {"turmas": 1, "vagas": 2}}
    metricas = calcular_metricas(alunos, estrutura, distribuicao, [], "Optimal", None)
    return ResultadoInterface(Path("amostra.xlsx"), b"planilha", distribuicao,
                              [{"Linha": "2, 3", "Nome": "João", "Motivo": "Nome duplicado no cadastro."}],
                              grupos, {k: len(v) for k, v in grupos.items()},
                              {"MANHÃ - A": (1, 1), "MANHÃ - B": (0, 0), "TARDE - C": (1, 0)}, 0, metricas)


class InterfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.janela = JanelaPrincipal()
        self.janela.show()
        self.app.processEvents()

    def tearDown(self):
        if self.janela._tarefa:
            self.janela._tarefa.wait(3000)
            self.app.processEvents()
        self.janela.close()
        self.janela.deleteLater()
        self.app.processEvents()

    def test_dashboard_desktop_exibe_dois_graficos_sem_paginacao(self):
        w = self.janela
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        w.mostrar_resultado(amostra())
        graficos = list(w.graficos)
        for _ in range(20):
            w.mudar_secao(1)
            w.mudar_secao(0)
        self.assertEqual(w.graficos, graficos)
        self.assertTrue(all(g.isVisible() for g in w.graficos))
        self.assertEqual(w.findChildren(QStackedWidget), [w.secoes])
        self.assertEqual(w.modo_dashboard, "desktop")
        self.assertFalse(w.controles_dashboard.isVisible())
        self.assertFalse(w.dashboard_anterior.isVisible())
        self.assertFalse(w.dashboard_proximo.isVisible())
        self.assertFalse(w.pagina_dashboard.isVisible())
        self.assertEqual(w.grade_indicadores.colunas, 6)
        self.assertEqual(w.grade_resumos.colunas, 2)
        self.assertEqual(w.graficos[1].dados["MANHÃ - B"], (0, 0))
        self.assertEqual(w.graficos[0].capacidades["MANHÃ - A"], 2)
        self.assertEqual(len(w.indicadores), 6)
        self.assertEqual(w.detalhes_indicadores[0].text(), "de 3 alunos · 100,0%")
        self.assertEqual(w.indicadores[3].text(), "50,0%")
        self.assertEqual(w.indicadores[4].text(), "50,0%")
        self.assertEqual(w.detalhes_indicadores[4].text(), "3 vagas livres")
        self.assertEqual(w.diferencas_turmas["MANHÃ"].text(), "2 alunos")
        self.assertEqual(w.diferencas_turmas["TARDE"].text(), "0 aluno")
        self.assertEqual(w.variacao_genero.text(), "1 homem a mais")
        self.assertEqual(w.turmas_variacao_genero.text(), "TARDE - C")
        self.assertEqual(w.resumo_turnos["MANHÃ"]["alunos_alocados"].text(), "2 / 2")
        self.assertEqual(w.resumo_turnos["MANHÃ"]["vagas_ociosas"].text(), "2")

    def test_dashboard_reorganiza_graficos_e_cards_com_rolagem(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        self.app.processEvents()
        self.assertEqual(w.grade_graficos.colunas, 2)
        self.assertEqual(w.grade_indicadores.colunas, 6)
        w.resize(880, 600)
        self.app.processEvents()
        self.assertEqual(w.grade_graficos.colunas, 1)
        self.assertEqual(w.grade_indicadores.colunas, 3)
        self.assertEqual(w.grade_resumos.colunas, 1)
        self.assertTrue(w.controles_dashboard.isVisible())
        self.assertGreater(w.dashboard.verticalScrollBar().maximum(), 0)
        self.assertEqual(w.dashboard.horizontalScrollBar().maximum(), 0)
        self.assertEqual([g.isVisible() for g in w.graficos], [True, False])
        self.assertTrue(all(p.height() == 330 for p in w.grade_graficos.widgets))
        graficos = list(w.graficos)
        w.resize(LARGURA_CARDS_TRES_COLUNAS - 80, 600)
        self.app.processEvents()
        self.assertEqual(w.grade_indicadores.colunas, 2)
        self.assertEqual(w.dashboard.horizontalScrollBar().maximum(), 0)
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        self.app.processEvents()
        self.assertEqual(w.grade_graficos.colunas, 2)
        self.assertEqual(w.grade_indicadores.colunas, 6)
        self.assertEqual(w.graficos, graficos)

    def test_carrossel_compacto_alterna_os_mesmos_graficos(self):
        w = self.janela
        w.resize(LARGURA_DASHBOARD_DESKTOP - 100, 880)
        w.mostrar_resultado(amostra())
        self.app.processEvents()
        self.assertEqual(w.modo_dashboard, "compacto")
        self.assertEqual([g.isVisible() for g in w.graficos], [True, False])
        self.assertTrue(w.controles_dashboard.isVisible())
        self.assertEqual(w.pagina_dashboard.text(), "1 / 2")
        for _ in range(3):
            w.dashboard_proximo.click()
            self.assertEqual([g.isVisible() for g in w.graficos], [False, True])
            self.assertEqual(w.pagina_dashboard.text(), "2 / 2")
            w.dashboard_proximo.click()
            self.assertEqual([g.isVisible() for g in w.graficos], [True, False])
        w.dashboard_anterior.click()
        self.assertEqual([g.isVisible() for g in w.graficos], [False, True])
        self.assertEqual(w.pagina_dashboard.text(), "2 / 2")
        self.assertTrue(all(p.isVisible() for p in w.grade_resumos.widgets))
        self.assertEqual(w.grade_resumos.colunas, 1)

    def test_resize_preserva_resultado_selecao_rolagem_e_conexoes(self):
        w = self.janela
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        resultado = amostra()
        w.mostrar_resultado(resultado)
        w.turma.setCurrentText("TARDE - C")
        # Muitas linhas tornam a preservação da rolagem verificável.
        dados = {f"MANHÃ - {i}": 2 for i in range(32)}
        dados["TARDE - C"] = 1
        w.graficos[0].definir(dados)
        w.graficos[1].definir({nome: (1, 1) for nome in dados})
        self.app.processEvents()
        for area, valor in zip(w.areas_graficos, (80, 100)):
            area.verticalScrollBar().setValue(valor)
        graficos = list(w.graficos)
        paineis = list(w.grade_graficos.widgets)
        resumos = list(w.grade_resumos.widgets)
        indicadores = [r.text() for r in w.indicadores]
        dados_antes = [dict(g.dados) for g in graficos]
        conexoes = [g.receivers("2turma_clicada(QString)") for g in graficos]
        quantidade_widgets = len(w.findChildren(QWidget))
        with patch("ensalamento.resolver", side_effect=AssertionError("Resize não resolve a instância")):
            for _ in range(3):
                for largura in (LARGURA_DASHBOARD_DESKTOP - 100, LARGURA_DASHBOARD_DESKTOP + 80):
                    w.resize(largura, 880)
                    self.app.processEvents()
                    self.assertIs(w.resultado, resultado)
                    self.assertEqual(w.graficos, graficos)
                    self.assertEqual(w.grade_graficos.widgets, paineis)
                    self.assertEqual(w.grade_resumos.widgets, resumos)
                    self.assertEqual([g.dados for g in graficos], dados_antes)
                    self.assertEqual([r.text() for r in w.indicadores], indicadores)
                    self.assertEqual(w.turma.currentText(), "TARDE - C")
                    self.assertTrue(all(g.selecionada == "TARDE - C" for g in graficos))
                    self.assertEqual([a.verticalScrollBar().value() for a in w.areas_graficos], [80, 100])
        self.assertEqual(len(w.findChildren(QWidget)), quantidade_widgets)
        self.assertEqual(w.findChildren(Grafico), graficos)
        self.assertEqual([g.receivers("2turma_clicada(QString)") for g in graficos], conexoes)
        w.resize(LARGURA_DASHBOARD_DESKTOP - 100, 880)
        self.app.processEvents()
        with patch.object(w, "mudar_dashboard", wraps=w.mudar_dashboard) as mudar:
            w.dashboard_proximo.click()
        mudar.assert_called_once_with(1)
        self.assertEqual(w.indice_dashboard, 1)
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        self.app.processEvents()
        w.resize(LARGURA_DASHBOARD_DESKTOP - 100, 880)
        self.app.processEvents()
        self.assertEqual(w.pagina_dashboard.text(), "2 / 2")
        self.assertEqual([g.isVisible() for g in graficos], [False, True])
        graficos[1].turma_clicada.emit("MANHÃ - A")
        self.assertEqual(w.turma.currentText(), "MANHÃ - A")
        self.assertEqual(w.secoes.currentIndex(), 1)

    def test_resize_reorganiza_somente_ao_cruzar_breakpoint(self):
        w = self.janela
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        self.app.processEvents()
        with patch.object(w, "reorganizar_dashboard", wraps=w.reorganizar_dashboard) as reorganizar:
            for largura in (LARGURA_DASHBOARD_DESKTOP + 100, LARGURA_DASHBOARD_DESKTOP + 120):
                w.resize(largura, 880)
                self.app.processEvents()
            reorganizar.assert_not_called()
            w.resize(LARGURA_DASHBOARD_DESKTOP - 10, 880)
            self.app.processEvents()
            reorganizar.assert_called_once()
            for largura in (LARGURA_DASHBOARD_DESKTOP - 20, LARGURA_DASHBOARD_DESKTOP - 30):
                w.resize(largura, 880)
                self.app.processEvents()
            self.assertEqual(reorganizar.call_count, 1)
            w.resize(LARGURA_DASHBOARD_DESKTOP + 10, 880)
            self.app.processEvents()
            self.assertEqual(reorganizar.call_count, 2)

    def test_full_hd_exibe_graficos_e_resumos_lado_a_lado(self):
        w = self.janela
        resultado = amostra()
        w.mostrar_resultado(resultado)
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 1080)
        self.app.processEvents()
        self.assertTrue(all(g.isVisible() for g in w.graficos))
        w.resize(1920, 1080)
        self.app.processEvents()
        self.assertEqual(w.modo_dashboard, "desktop")
        self.assertFalse(w.controles_dashboard.isVisible())
        self.assertTrue(all(g.isVisible() for g in w.graficos))
        self.assertEqual(w.grade_indicadores.colunas, 6)
        self.assertEqual(w.grade_resumos.colunas, 2)
        self.assertEqual(w.grade_qualidade.colunas, 2)
        self.assertIs(w.resultado, resultado)

    def test_resumo_por_turno_tem_tabela_centralizada_de_cinco_linhas(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        w.resize(1920, 1080)
        self.app.processEvents()
        self.assertEqual([r.text() for r in w.rotulos_resumo_turnos.values()],
                         ["Alocados", "Sem turma", "Capacidade", "Ocupação", "Vagas livres"])
        self.assertEqual([r.text() for r in w.cabecalhos_turnos.values()], ["MANHÃ", "TARDE"])
        for cabecalho in w.cabecalhos_turnos.values():
            self.assertEqual(cabecalho.alignment(), Qt.AlignmentFlag.AlignCenter)
        for turno, valores in w.resumo_turnos.items():
            self.assertEqual(len(valores), 5)
            for rotulo in valores.values():
                self.assertEqual(rotulo.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertNotIn("alunos_disponiveis", valores)
            self.assertNotIn("taxa_ociosidade", valores)
        self.assertEqual(w.resumo_turnos["TARDE"]["alunos_alocados"].text(), "1 / 1")
        self.assertLessEqual(w.tabela_resumo_turnos.width(), 520)
        self.assertLess(w.tabela_resumo_turnos.width(), w.grade_resumos.widgets[1].width())
        w.resize(680, 600)
        self.app.processEvents()
        self.assertEqual(w.grade_resumos.colunas, 1)
        self.assertEqual(w.grade_qualidade.colunas, 1)
        self.assertEqual(w.dashboard.horizontalScrollBar().maximum(), 0)

    def test_qualidade_mostra_empates_e_oculta_turmas_quando_equilibrado(self):
        w = self.janela
        resultado = amostra()
        # Somente dados de apresentação; a fórmula continua em metricas.py.
        resultado.metricas["destaques"]["variacao_genero"] = {
            "quantidade": 3, "predominancias": ["mulheres", "homens"],
            "turmas": ["MANHÃ - A", "TARDE - C"],
        }
        w.mostrar_resultado(resultado)
        self.assertEqual(w.variacao_genero.text(), "3 mulheres a mais · 3 homens a mais")
        self.assertEqual(w.turmas_variacao_genero.text(), "MANHÃ - A, TARDE - C")
        resultado.metricas["destaques"]["variacao_genero"] = {
            "quantidade": 0, "predominancias": ["equilibrado"], "turmas": ["MANHÃ - A"],
        }
        w.mostrar_resultado(resultado)
        self.assertEqual(w.variacao_genero.text(), "Equilibrado")
        self.assertTrue(w.turmas_variacao_genero.isHidden())
        self.assertEqual(w.turmas_variacao_genero.text(), "")

    def test_dashboard_usa_metricas_como_fonte(self):
        resultado = amostra()
        resultado = replace(resultado, totais={"MANHÃ - A": 999}, sexos={"MANHÃ - A": (999, 999)}, sem_turma=999)
        self.janela.mostrar_resultado(resultado)
        self.assertEqual(self.janela.indicadores[1].text(), "0")
        self.assertEqual(sum(self.janela.graficos[0].dados.values()), 3)
        self.assertEqual(self.janela.graficos[1].dados["MANHÃ - A"], (1, 1))

    def test_indicadores_combo_e_graficos_com_alunos_sem_turma(self):
        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta) / "entrada.xlsx"
            criar_entrada_sem_vagas(origem)
            resultado = processar_planilha(origem)
        w = self.janela
        w.mostrar_resultado(resultado)
        self.assertEqual(w.indicadores[0].text(), "403")
        self.assertEqual(w.indicadores[1].text(), "12")
        self.assertEqual(w.detalhes_indicadores[0].text(), "de 415 alunos · 97,1%")
        self.assertEqual([w.turma.itemText(i) for i in range(w.turma.count())], list(resultado.grupos))
        self.assertNotIn("SEM TURMA", w.graficos[0].dados)
        self.assertNotIn("SEM TURMA", w.graficos[1].dados)
        self.assertEqual(w.graficos[0].dados, resultado.totais)
        self.assertEqual(w.graficos[1].dados, resultado.sexos)
        self.assertEqual(sum(w.graficos[0].dados.values()), 403)
        self.assertEqual(sum(sum(v) for v in w.graficos[1].dados.values()), 403)
        self.assertIn("ALUNOS SEM TURMA (12)", w.relatorio.toPlainText())

    def test_uma_turma_por_vez_busca_e_homonimos(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        self.assertEqual(w.modelo.rowCount(), 2)
        w.busca.setText("agata")
        self.assertEqual(w.filtro.rowCount(), 1)
        w.mudar_turma(1)
        self.assertEqual(w.modelo.rowCount(), 0)
        self.assertEqual(w.busca.text(), "")
        w.mudar_turma(1)
        self.assertEqual(w.modelo.rowCount(), 1)
        self.assertFalse(w.turma_proxima.isEnabled())
        self.assertIn("NOMES DUPLICADOS", w.relatorio.toPlainText())
        self.assertEqual(w.indicadores[0].text(), "3")

    def test_tabela_virtual_nao_cria_widgets_por_aluno_e_mantem_espaco(self):
        w = self.janela
        w.resize(880, 600)
        w.mostrar_resultado(amostra())
        w.mudar_secao(1)
        self.app.processEvents()
        quantidade = len(w.tabela.findChildren(QWidget))
        w.modelo.definir([amostra().distribuicao[0]] * 10000)
        self.app.processEvents()
        self.assertEqual(w.modelo.rowCount(), 10000)
        self.assertEqual(len(w.tabela.findChildren(QWidget)), quantidade)
        self.assertGreaterEqual(w.tabela.viewport().height(), 100)

    def test_secoes_ocupam_area_principal_e_preservam_estado(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        widgets = [w.secoes.widget(i) for i in range(3)]
        modelo = w.modelo
        w.mudar_secao(1)
        w.busca.setText("agata")
        reset = QSignalSpy(w.modelo.modelReset)
        for i in range(30):
            w.mudar_secao(i % 3)
        w.mudar_secao(1)
        self.app.processEvents()
        self.assertEqual(w.secoes.count(), 3)
        self.assertEqual([w.secoes.widget(i) for i in range(3)], widgets)
        self.assertIs(w.modelo, modelo)
        self.assertEqual(reset.count(), 0)
        self.assertEqual(w.busca.text(), "agata")
        self.assertEqual(w.filtro.rowCount(), 1)
        self.assertEqual([p.isVisible() for p in widgets], [False, True, False])
        self.assertGreater(w.tabela.viewport().height(), 300)
        w.mudar_secao(2)
        self.app.processEvents()
        self.assertGreater(w.relatorio.viewport().height(), 350)

    def test_animacao_unica_curta_e_encerrada_apos_navegacao(self):
        w = self.janela
        w.mudar_secao(1)
        w.mudar_secao(2)
        QTest.qWait(180)
        self.assertEqual(len(w.findChildren(QPropertyAnimation)), 1)
        self.assertEqual(w.navegacao.animacao.duration(), 120)
        self.assertEqual(w.navegacao.animacao.state(), QAbstractAnimation.State.Stopped)
        self.assertEqual(w.secoes.currentIndex(), 2)
        self.assertTrue(w.navegacao.botoes[2].isChecked())

    def test_clique_no_grafico_abre_a_secao_da_turma(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        w.busca.setText("agata")
        w.ir_para_turma("TARDE - C")
        self.assertEqual(w.secoes.currentIndex(), 1)
        self.assertEqual(w.turma.currentText(), "TARDE - C")
        self.assertEqual(w.filtro.rowCount(), 1)
        self.assertEqual(w.busca.text(), "")

    def test_calculo_em_background_mantem_eventos_da_interface(self):
        w = self.janela
        liberar = threading.Event()
        iniciou = threading.Event()
        def processar(_):
            iniciou.set()
            liberar.wait(3)
            return amostra()
        w.processador = processar
        w.definir_arquivo(Path("amostra.xlsx"))
        ticks = []
        timer = QTimer(w)
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        w.gerar_distribuicao()
        try:
            self.assertTrue(iniciou.wait(1))
            QTest.qWait(150)
            self.assertGreaterEqual(len(ticks), 3)
            self.assertFalse(w.importar.isEnabled())
            self.assertFalse(w.exportar.isEnabled())
            self.assertFalse(w.close())
        finally:
            liberar.set()
        limite = time.monotonic() + 3
        while w._ocupado and time.monotonic() < limite:
            QTest.qWait(10)
        timer.stop()
        self.assertFalse(w._ocupado)
        self.assertEqual(w.modelo.rowCount(), 2)
        self.assertTrue(w.exportar.isEnabled())

    def test_importar_outro_arquivo_limpa_resultado_anterior(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        w.definir_arquivo(Path("outra.xlsx"))
        self.assertIsNone(w.resultado)
        self.assertFalse(w.exportar.isEnabled())
        self.assertEqual(w.modelo.rowCount(), 0)
        self.assertEqual(w.graficos[0].dados, {})


if __name__ == "__main__":
    unittest.main()

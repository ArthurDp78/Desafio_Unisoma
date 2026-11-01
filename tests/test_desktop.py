"""Integração da UI desktop, cópia de trabalho e exportação sem recálculo."""
from collections import Counter
from dataclasses import replace
from io import BytesIO
import json
import os
import shutil
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from PySide6.QtCore import QAbstractAnimation, QPoint, QPropertyAnimation, QTimer, Qt
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QFrame, QProgressBar, QStackedWidget, QWidget

from apresentacao import ResultadoInterface, exportar_planilha, processar_planilha, relatorios_interface
from recursos import caminho_recurso
import ensalamento
from dados import Aluno
from interface_desktop import (
    Grafico, JanelaPrincipal,
    LARGURA_DASHBOARD_DESKTOP,
)
from metricas import calcular_metricas
from tema import ESPACO_SECOES


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
        self.assertEqual(w.grade_indicadores.colunas, 4)
        self.assertEqual(w.grade_resumos.colunas, 2)
        self.assertEqual(w.graficos[1].dados["MANHÃ - B"], (0, 0))
        self.assertEqual(w.graficos[0].capacidades["MANHÃ - A"], 2)
        self.assertEqual(len(w.indicadores), 4)
        self.assertEqual(w.detalhes_indicadores[0].text(), "100,0% dos alunos")
        self.assertEqual(w.indicadores[2].text(), "50,0%")
        self.assertEqual(w.indicadores[3].text(), "50,0%")
        self.assertEqual(w.detalhes_indicadores[3].text(), "3 vagas livres")
        self.assertEqual(w.diferencas_turmas["MANHÃ"].text(), "2 alunos")
        self.assertEqual(w.diferencas_turmas["TARDE"].text(), "0 aluno")
        self.assertEqual(w.variacao_genero.text(), "1 homem a mais")
        self.assertEqual(w.turmas_variacao_genero.text(), "Tarde · C")
        self.assertEqual(w.resumo_turnos["MANHÃ"]["alunos_alocados"].text(), "2 / 2")
        self.assertEqual(w.resumo_turnos["MANHÃ"]["vagas_ociosas"].text(), "2")

    def test_dashboard_reorganiza_graficos_e_cards_com_rolagem(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        self.app.processEvents()
        self.assertEqual(w.grade_graficos.colunas, 2)
        self.assertEqual(w.grade_indicadores.colunas, 4)
        w.resize(880, 600)
        self.app.processEvents()
        self.assertEqual(w.grade_graficos.colunas, 1)
        self.assertEqual(w.grade_indicadores.colunas, 2)
        self.assertEqual(w.grade_resumos.colunas, 1)
        self.assertTrue(w.controles_dashboard.isVisible())
        self.assertGreater(w.dashboard.verticalScrollBar().maximum(), 0)
        self.assertEqual(w.dashboard.horizontalScrollBar().maximum(), 0)
        self.assertEqual([g.isVisible() for g in w.graficos], [True, False])
        self.assertTrue(all(p.height() >= 400 for p in w.grade_graficos.widgets))
        graficos = list(w.graficos)
        w.resize(740, 600)
        self.app.processEvents()
        self.assertEqual(w.grade_indicadores.colunas, 2)
        self.assertEqual(w.dashboard.horizontalScrollBar().maximum(), 0)
        w.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        self.app.processEvents()
        self.assertEqual(w.grade_graficos.colunas, 2)
        self.assertEqual(w.grade_indicadores.colunas, 4)
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
        self.assertEqual(w.grade_indicadores.colunas, 4)
        self.assertEqual(w.grade_resumos.colunas, 2)
        self.assertEqual(w.grade_qualidade.colunas, 2)
        self.assertIs(w.resultado, resultado)

    def test_resumo_por_turno_transposto_com_separadores(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        w.resize(1920, 1080)
        self.app.processEvents()
        self.assertEqual([r.text() for r in w.rotulos_resumo_turnos.values()],
                         ["Turno", "Alocados", "Sem turma", "Capacidade", "Ocupação", "Vagas livres"])
        self.assertEqual([r.text() for r in w.cabecalhos_turnos.values()], ["Manhã", "Tarde"])
        for cabecalho in w.cabecalhos_turnos.values():
            self.assertEqual(cabecalho.alignment(), Qt.AlignmentFlag.AlignCenter)
        for turno, valores in w.resumo_turnos.items():
            self.assertEqual(len(valores), 5)
            for rotulo in valores.values():
                self.assertEqual(rotulo.alignment(), Qt.AlignmentFlag.AlignCenter)
            self.assertNotIn("alunos_disponiveis", valores)
            self.assertNotIn("taxa_ociosidade", valores)
        self.assertEqual(w.resumo_turnos["TARDE"]["alunos_alocados"].text(), "1 / 1")
        grade = w.tabela_resumo_turnos.layout()
        self.assertEqual(grade.itemAtPosition(0, 0).widget().text(), "Turno")
        self.assertIs(grade.itemAtPosition(2, 0).widget(), w.cabecalhos_turnos["MANHÃ"])
        self.assertIs(grade.itemAtPosition(4, 0).widget(), w.cabecalhos_turnos["TARDE"])
        self.assertEqual(len(w.tabela_resumo_turnos.findChildren(QFrame, "separador")), 2)
        self.assertLess(w.tabela_resumo_turnos.width(), w.grade_resumos.widgets[1].width())
        w.resize(680, 600)
        self.app.processEvents()
        self.assertEqual(w.grade_resumos.colunas, 1)
        self.assertIn(w.grade_qualidade.colunas, (1, 2))
        self.assertEqual(w.dashboard.horizontalScrollBar().maximum(), 0)

    def test_eixo_horizontal_permanece_fixo_ao_rolar_barras(self):
        w = self.janela
        w.resize(1920, 1080)
        w.mostrar_resultado(amostra())
        for grafico in w.graficos:
            grafico.definir({f"Turma {i}": (3, 4) if grafico.por_sexo else 7 for i in range(40)})
        QTest.qWait(50)  # Conclui o layout após o aparecimento das barras de rolagem.
        for area, eixo in zip(w.areas_graficos, w.eixos_graficos):
            QTest.qWait(20)
            self.assertFalse(area.isAncestorOf(eixo))
            self.assertEqual(eixo.titulo, "Quantidade de alunos")
            self.assertTrue(eixo.isVisible())
            self.assertTrue(w.dashboard.viewport().rect().contains(
                eixo.mapTo(w.dashboard.viewport(), eixo.rect().bottomRight())))
            imagem = eixo.grab().toImage()
            posicao = eixo.mapToGlobal(QPoint(0, 0))
            self.assertGreater(area.verticalScrollBar().maximum(), 0)
            area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
            self.app.processEvents()
            self.assertEqual(eixo.mapToGlobal(QPoint(0, 0)), posicao)
            self.assertEqual(eixo.grab().toImage(), imagem)

    def test_navegacao_e_recursos_svg_no_codigo_e_no_pacote(self):
        w = self.janela
        self.assertEqual([r.text() for r in w.navegacao.rotulos],
                         ["Dashboard", "Alunos por turma", "Inconsistências e avisos"])
        self.assertEqual(w.secoes.count(), 3)
        self.assertEqual(len(w.navegacao.findChildren(QSvgWidget)), 3)
        self.assertTrue(all(i.renderer().isValid() for i in w.navegacao.findChildren(QSvgWidget)))
        w.mostrar_resultado(amostra())
        for botao in w.navegacao.botoes:
            self.assertTrue(botao.shortcut().isEmpty())
            self.assertNotIn("Alt+", botao.toolTip())
        w.mudar_secao(2)
        QTest.keyClick(w.navegacao.botoes[2], Qt.Key.Key_1, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(w.secoes.currentIndex(), 2)
        w.navegacao.botoes[0].click()
        self.assertEqual(w.secoes.currentIndex(), 0)
        icones = list(caminho_recurso("assets", "icons").glob("*.svg"))
        self.assertIn("chevron_down.svg", {arquivo.name for arquivo in icones})
        for arquivo in icones:
            self.assertTrue(QSvgRenderer(str(arquivo)).isValid(), str(arquivo))
        with tempfile.TemporaryDirectory() as pasta:
            shutil.copytree(caminho_recurso("assets"), Path(pasta) / "assets")
            with patch.object(sys, "_MEIPASS", pasta, create=True):
                arquivo = caminho_recurso("assets", "icons", "tab_inconsistencias.svg")
                self.assertEqual(arquivo, Path(pasta) / "assets" / "icons" / "tab_inconsistencias.svg")
                self.assertTrue(QSvgRenderer(str(arquivo)).isValid())
                self.assertTrue(QSvgRenderer(str(caminho_recurso("assets", "icons", "chevron_down.svg"))).isValid())

    def test_avisos_e_inconsistencias_separam_apenas_a_apresentacao(self):
        resultado = amostra()
        registros = [
            {"Linha": 2, "Nome": "Duplicado", "Motivo": "Nome duplicado no cadastro."},
            {"Linha": 3, "Nome": "Normalizado", "Motivo": "Sexo normalizado."},
            {"Linha": 4, "Nome": "Inválido", "Motivo": "Sexo inválido; registro não foi alocado."},
            {"Linha": 5, "Nome": "Sem vaga", "Motivo": "Aluno sem turma no resultado do modelo."},
            {"Linha": 6, "Nome": "Misto", "Motivo": "Nome normalizado. Sexo inválido; registro não foi alocado."},
        ]
        resultado = replace(resultado, inconsistencias=registros)
        self.janela.mostrar_resultado(resultado)
        erros, avisos = relatorios_interface(resultado)
        self.assertIn("Inválido", erros)
        self.assertIn("Sem vaga", erros)
        self.assertNotIn("Duplicado", erros)
        self.assertIn("Duplicado", avisos)
        self.assertIn("Normalizado", avisos)
        self.assertNotIn("Inválido", avisos)
        self.assertIn("Misto", erros)
        self.assertNotIn("Misto", avisos)
        self.assertEqual(resultado.inconsistencias, registros)
        self.assertIn("Duplicado", resultado.relatorio())
        self.assertIn("Inválido", resultado.relatorio())
        self.assertEqual(self.janela.relatorio.toPlainText(), erros)
        self.assertEqual(self.janela.avisos.toPlainText(), avisos)
        self.assertEqual([c.text() for c in self.janela.contadores_ocorrencias], ["3", "2"])
        self.assertEqual(self.janela.navegacao.badge.text(), "5")
        self.assertFalse(self.janela.navegacao.badge.isHidden())
        self.janela.mostrar_resultado(replace(resultado, inconsistencias=[]))
        self.assertEqual([c.text() for c in self.janela.contadores_ocorrencias], ["0", "0"])
        self.assertTrue(self.janela.navegacao.badge.isHidden())
        self.assertIn("Nenhuma inconsistência encontrada.", self.janela.relatorio.toPlainText())
        self.assertIn("Nenhum aviso gerado.", self.janela.avisos.toPlainText())

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
        self.assertEqual(w.turmas_variacao_genero.text(), "Manhã · A, Tarde · C")
        self.assertEqual(w.turmas_variacao_genero.toolTip(), "Manhã · A\nTarde · C")
        turmas = [f"TARDE - {letra}" for letra in ("P", "R", "S", "U", "W", "Y", "AA", "AC")]
        resultado.metricas["destaques"]["variacao_genero"]["turmas"] = turmas
        w.mostrar_resultado(resultado)
        QTest.qWait(40)
        self.assertEqual(w.turmas_variacao_genero.text(), "Tarde · P, Tarde · R, Tarde · S, Tarde · U, ...")
        self.assertEqual(w.turmas_variacao_genero.toolTip().splitlines(),
                         [f"Tarde · {t.split(' - ')[1]}" for t in turmas])
        self.assertEqual(resultado.metricas["destaques"]["variacao_genero"]["turmas"], turmas)
        for largura, altura in ((1920, 1080), (1366, 768), (680, 600)):
            w.resize(largura, altura)
            QTest.qWait(40)
            self.assertEqual(w.dashboard.horizontalScrollBar().maximum(), 0)
            rotulo = w.turmas_variacao_genero
            self.assertGreaterEqual(rotulo.height(), rotulo.heightForWidth(rotulo.width()))
        resultado.metricas["destaques"]["variacao_genero"] = {
            "quantidade": 0, "predominancias": ["equilibrado"], "turmas": ["MANHÃ - A"],
        }
        w.mostrar_resultado(resultado)
        self.assertEqual(w.variacao_genero.text(), "Equilibrado")
        self.assertTrue(w.turmas_variacao_genero.isHidden())
        self.assertEqual(w.turmas_variacao_genero.text(), "")
        self.assertEqual(w.turmas_variacao_genero.toolTip(), "")

    def test_carregamento_oculto_na_selecao_e_no_resultado_sem_reservar_espaco(self):
        w = self.janela
        self.assertTrue(w.carregamento.isHidden())
        self.assertFalse(w.progresso.isVisible())
        self.assertFalse(w.mensagem_carregamento.isVisible())
        self.assertIsNone(w.findChild(QFrame, "faixaStatus"))
        self.assertEqual(w.findChildren(QProgressBar), [w.progresso])
        principal = w.centralWidget().widget().layout()
        self.assertEqual(principal.indexOf(w.carregamento), principal.indexOf(w.nome_arquivo.parentWidget()) + 1)
        self.assertEqual(principal.indexOf(w.navegacao), principal.indexOf(w.carregamento) + 1)
        w.definir_arquivo(Path("amostra.xlsx"))
        QTest.qWait(30)
        posicao_abas = w.navegacao.y()
        w.mostrar_resultado(amostra())
        QTest.qWait(30)
        self.assertTrue(w.carregamento.isHidden())
        self.assertEqual(w.navegacao.y(), posicao_abas)
        w.definir_arquivo(Path("outra.xlsx"))
        self.assertTrue(w.carregamento.isHidden())

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
        self.assertEqual(w.indicadores[0].text(), "403 / 415")
        self.assertEqual(w.indicadores[1].text(), "12")
        self.assertEqual(w.detalhes_indicadores[0].text(), "97,1% dos alunos")
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
        self.assertIn("NOMES DUPLICADOS", w.avisos.toPlainText())
        self.assertEqual(w.indicadores[0].text(), "3 / 3")

    def test_filtros_de_sexo_disponibilidade_busca_e_turma_se_combinam(self):
        w = self.janela
        resultado = amostra()
        metricas_antes = json.dumps(resultado.metricas, sort_keys=True)
        w.mostrar_resultado(resultado)
        indicadores_antes = [r.text() for r in w.indicadores]
        self.assertEqual([w.filtro_sexo.itemText(i) for i in range(3)], ["Todos", "Feminino", "Masculino"])
        self.assertEqual([w.filtro_disponibilidade.itemText(i) for i in range(3)], ["Todas", "Manhã", "Tarde"])
        w.filtro_sexo.setCurrentText("Feminino")
        self.assertEqual(w.filtro.rowCount(), 1)
        self.assertEqual(w.filtro.index(0, 0).data(), "Ágata")
        self.assertEqual(w.modelo.rowCount(), 2)
        self.assertEqual(w.contagem.text(), "1 de 2 alunos nesta turma")
        w.busca.setText("AGATA")
        self.assertEqual(w.filtro.rowCount(), 1)
        w.busca.setText("joao")
        self.assertEqual(w.filtro.rowCount(), 0)
        self.assertEqual(w.contagem.text(), "0 de 2 alunos nesta turma")
        w.filtro_sexo.setCurrentText("Masculino")
        self.assertEqual(w.filtro.rowCount(), 1)
        w.filtro_disponibilidade.setCurrentText("Tarde")
        self.assertEqual(w.filtro.rowCount(), 0)
        w.turma.setCurrentText("TARDE - C")
        self.assertEqual(w.busca.text(), "")  # Mantém o comportamento anterior ao trocar a turma.
        self.assertEqual(w.filtro.rowCount(), 1)
        self.assertEqual(w.contagem.text(), "1 de 1 alunos nesta turma")
        w.filtro_disponibilidade.setCurrentText("Manhã")
        self.assertEqual(w.filtro.rowCount(), 0)
        w.filtro_disponibilidade.setCurrentText("Todas")
        w.filtro_sexo.setCurrentText("Todos")
        w.turma.setCurrentText("MANHÃ - A")
        self.assertEqual(w.filtro.rowCount(), 2)
        self.assertIs(w.modelo.registros, resultado.grupos["MANHÃ - A"])
        self.assertEqual(json.dumps(resultado.metricas, sort_keys=True), metricas_antes)
        self.assertEqual([r.text() for r in w.indicadores], indicadores_antes)

    def test_controles_de_alunos_refluem_e_preservam_filtros(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        w.mudar_secao(1)
        w.filtro_sexo.setCurrentText("Masculino")
        w.filtro_disponibilidade.setCurrentText("Manhã")
        w.busca.setText("joao")
        modelo = w.modelo
        for largura, altura, colunas in ((1920, 1080, 4), (1366, 768, 4), (680, 600, 2)):
            w.resize(largura, altura)
            QTest.qWait(50)
            self.assertEqual(w.controles_alunos.colunas, colunas)
            self.assertEqual(w.centralWidget().horizontalScrollBar().maximum(), 0)
            self.assertIs(w.modelo, modelo)
            self.assertEqual(w.filtro.rowCount(), 1)
            w.mudar_secao(0)
            w.mudar_secao(1)
            self.assertEqual(w.filtro_sexo.currentText(), "Masculino")
            self.assertEqual(w.filtro_disponibilidade.currentText(), "Manhã")
            self.assertEqual(w.busca.text(), "joao")
        self.assertIs(w.turma.parentWidget(), w.turma_anterior.parentWidget())
        self.assertIs(w.turma.parentWidget(), w.turma_proxima.parentWidget())
        self.assertEqual(w.turma_anterior.toolTip(), "Turma anterior")
        self.assertEqual(w.turma_proxima.toolTip(), "Próxima turma")
        self.assertFalse(w.turma_anterior.isEnabled())
        w.turma_proxima.click()
        self.assertEqual(w.turma.currentText(), "MANHÃ - B")
        w.turma_anterior.click()
        self.assertEqual(w.turma.currentText(), "MANHÃ - A")
        w.definir_arquivo(Path("outra.xlsx"))
        self.assertEqual(w.filtro_sexo.currentText(), "Todos")
        self.assertEqual(w.filtro_disponibilidade.currentText(), "Todas")
        self.assertFalse(w.filtro_sexo.isEnabled())
        self.assertFalse(w.filtro_disponibilidade.isEnabled())

    def test_dashboard_cede_apenas_o_pequeno_excesso_vertical(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        for altura in (1080, 1040, 1024, 1000):
            w.resize(1920, altura)
            QTest.qWait(60)
            self.assertEqual(w.dashboard.verticalScrollBar().maximum(), 0)
            preferida = int(altura * 0.48)
            self.assertLessEqual(preferida - w.grade_graficos.height(), 32)
            self.assertGreaterEqual(w.grade_graficos.height(), 400)
        w.resize(1920, 1080)
        QTest.qWait(60)
        self.assertEqual(w.grade_graficos.height(), int(1080 * 0.48))

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
        QTest.qWait(40)
        self.assertLess(w.relatorio.viewport().height(), 60)
        self.assertGreater(w.avisos.viewport().height(), w.relatorio.viewport().height())

    def test_ocorrencias_vazias_sao_compactas_e_preservam_espacamento(self):
        w = self.janela
        w.mostrar_resultado(replace(amostra(), inconsistencias=[]))
        w.mudar_secao(2)
        for largura, altura in ((1920, 1080), (1366, 768), (680, 600)):
            w.resize(largura, altura)
            QTest.qWait(40)
            primeira, segunda = w.paineis_ocorrencias
            self.assertEqual(primeira.y(), 0)
            self.assertEqual(segunda.y() - primeira.y() - primeira.height(), ESPACO_SECOES)
            self.assertLess(primeira.height(), 180)
            self.assertLess(segunda.height(), 180)
            self.assertEqual(w.ocorrencias.horizontalScrollBar().maximum(), 0)
            self.assertEqual([c.text() for c in w.contadores_ocorrencias], ["0", "0"])

    def test_ocorrencias_longas_usam_scroll_da_pagina_e_reajustam_linhas(self):
        w = self.janela
        registros = [{"Linha": i + 2, "Nome": f"Aluno {i}",
                      "Motivo": "Nome normalizado. " + "Descrição da normalização automática. " * 8}
                     for i in range(30)]
        resultado = replace(amostra(), inconsistencias=registros)
        w.mostrar_resultado(resultado)
        w.mudar_secao(2)
        alturas = []
        for largura, altura in ((1366, 768), (680, 600), (1920, 1080)):
            w.resize(largura, altura)
            QTest.qWait(60)
            alturas.append(w.avisos.height())
            self.assertGreater(w.ocorrencias.verticalScrollBar().maximum(), 0)
            self.assertEqual(w.ocorrencias.horizontalScrollBar().maximum(), 0)
            self.assertEqual(w.avisos.verticalScrollBar().maximum(), 0)
            self.assertEqual(w.avisos.horizontalScrollBar().maximum(), 0)
            cursor = w.avisos.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.assertLessEqual(w.avisos.cursorRect(cursor).bottom(), w.avisos.viewport().height())
            self.assertEqual(w.avisos.toPlainText(), relatorios_interface(resultado)[1])
            w.ocorrencias.verticalScrollBar().setValue(w.ocorrencias.verticalScrollBar().maximum())
            self.app.processEvents()
            painel = w.paineis_ocorrencias[1]
            fim = painel.mapTo(w.ocorrencias.viewport(), painel.rect().bottomLeft())
            self.assertTrue(w.ocorrencias.viewport().rect().contains(fim))
        self.assertGreater(alturas[1], alturas[0])
        self.assertLess(alturas[2], alturas[1])

    def test_abas_tem_altura_comum_e_larguras_equivalentes(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        for largura, altura in ((1920, 1080), (1366, 768), (680, 600)):
            w.resize(largura, altura)
            QTest.qWait(40)
            botoes = w.navegacao.botoes
            self.assertEqual(len({b.height() for b in botoes}), 1)
            if largura >= 1366:
                larguras = [b.width() for b in botoes]
                self.assertLessEqual(max(larguras) - min(larguras), 1)
            centros = [r.mapTo(w.navegacao, r.rect().center()).y() for r in w.navegacao.rotulos]
            self.assertLessEqual(max(centros) - min(centros), 1)
            for rotulo in w.navegacao.rotulos:
                self.assertGreaterEqual(rotulo.width(), rotulo.fontMetrics().horizontalAdvance(rotulo.text()))
            self.assertEqual(w.centralWidget().horizontalScrollBar().maximum(), 0)

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
        QTest.qWait(30)
        posicao_abas = w.navegacao.y()
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
            self.assertFalse(w.gerar.isEnabled())
            self.assertFalse(w.exportar.isEnabled())
            self.assertTrue(w.mensagem_carregamento.isVisible())
            self.assertEqual(w.mensagem_carregamento.text(), "Aguarde. A distribuição está sendo gerada.")
            self.assertTrue(w.progresso.isVisible())
            self.assertEqual((w.progresso.minimum(), w.progresso.maximum()), (0, 0))
            self.assertGreater(w.navegacao.y(), posicao_abas)
            self.assertFalse(w.close())
        finally:
            liberar.set()
        limite = time.monotonic() + 3
        while w._ocupado and time.monotonic() < limite:
            QTest.qWait(10)
        timer.stop()
        self.assertFalse(w._ocupado)
        QTest.qWait(30)
        self.assertTrue(w.carregamento.isHidden())
        self.assertFalse(w.mensagem_carregamento.isVisible())
        self.assertFalse(w.progresso.isVisible())
        self.assertEqual(w.navegacao.y(), posicao_abas)
        self.assertTrue(w.gerar.isEnabled())
        self.assertEqual(w.modelo.rowCount(), 2)
        self.assertTrue(w.exportar.isEnabled())

    def test_falha_no_calculo_remove_mensagem_e_linha_de_carregamento(self):
        w = self.janela
        def processar(_):
            raise ValueError("Falha de teste")
        w.processador = processar
        w.definir_arquivo(Path("amostra.xlsx"))
        with patch("interface_desktop.QMessageBox.critical") as alerta:
            w.gerar_distribuicao()
            limite = time.monotonic() + 3
            while w._ocupado and time.monotonic() < limite:
                QTest.qWait(10)
            alerta.assert_called_once_with(w, "Operação não concluída", "Falha de teste")
        self.assertFalse(w._ocupado)
        self.assertTrue(w.carregamento.isHidden())
        self.assertFalse(w.progresso.isVisible())
        self.assertFalse(w.mensagem_carregamento.isVisible())
        self.assertTrue(w.gerar.isEnabled())

    def test_exportacao_nao_exibe_carregamento_da_distribuicao(self):
        w = self.janela
        liberar = threading.Event()
        iniciou = threading.Event()
        def exportar(_, destino):
            iniciou.set()
            liberar.wait(3)
            return destino
        w.exportador = exportar
        w.definir_arquivo(Path("amostra.xlsx"))
        w.mostrar_resultado(amostra())
        w.exportar_para(Path("saida.xlsx"))
        try:
            self.assertTrue(iniciou.wait(1))
            QTest.qWait(40)
            self.assertTrue(w._ocupado)
            self.assertTrue(w.carregamento.isHidden())
            self.assertFalse(w.mensagem_carregamento.isVisible())
            self.assertFalse(w.progresso.isVisible())
        finally:
            liberar.set()
        limite = time.monotonic() + 3
        while w._ocupado and time.monotonic() < limite:
            QTest.qWait(10)
        self.assertFalse(w._ocupado)
        self.assertTrue(w.carregamento.isHidden())
        self.assertTrue(w.gerar.isEnabled())
        self.assertTrue(w.exportar.isEnabled())

    def test_importar_outro_arquivo_limpa_resultado_anterior(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        w.definir_arquivo(Path("outra.xlsx"))
        self.assertIsNone(w.resultado)
        self.assertFalse(w.exportar.isEnabled())
        self.assertEqual(w.modelo.rowCount(), 0)
        self.assertEqual(w.graficos[0].dados, {})
        self.assertTrue(w.navegacao.badge.isHidden())
        self.assertEqual([c.text() for c in w.contadores_ocorrencias], ["0", "0"])


if __name__ == "__main__":
    unittest.main()

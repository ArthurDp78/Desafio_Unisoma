"""Integração da UI desktop, cópia de trabalho e exportação sem recálculo."""
from collections import Counter
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
from PySide6.QtWidgets import QApplication, QWidget

from apresentacao import ResultadoInterface, exportar_planilha, processar_planilha
import ensalamento
from interface_desktop import JanelaPrincipal
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
        self.assertTrue({"resumo", "por_turno", "turmas", "situacao_turmas", "nao_alocados",
                         "balanceamento", "destaques"}.issubset(resultado.metricas))
        resumo = resultado.metricas["resumo"]
        self.assertEqual(resumo["alunos_alocados"], len(resultado.distribuicao))
        self.assertEqual(resumo["alunos_sem_turma"], resultado.sem_turma)
        self.assertEqual(resumo["total_turmas"], len(resultado.grupos))
        self.assertEqual(resumo["status_solver"], argumentos["status_solver"])
        self.assertEqual(resumo["valor_objetivo"], argumentos["valor_objetivo"])
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
            self.assertEqual(resultado.metricas["resumo"]["status_solver"], "Optimal")
            self.assertEqual(resultado.metricas["resumo"]["valor_objetivo"], 0.0)
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
            self.assertEqual(resultado.metricas["resumo"]["valor_objetivo"], 36.0)
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
    return ResultadoInterface(Path("amostra.xlsx"), b"planilha", [r for g in grupos.values() for r in g],
                              [{"Linha": "2, 3", "Nome": "João", "Motivo": "Nome duplicado no cadastro."}],
                              grupos, {k: len(v) for k, v in grupos.items()},
                              {"MANHÃ - A": (1, 1), "MANHÃ - B": (0, 0), "TARDE - C": (1, 0)}, 0, {})


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

    def test_carrossel_tem_dois_dashboards_sem_recriar_widgets(self):
        w = self.janela
        w.mostrar_resultado(amostra())
        graficos = list(w.graficos)
        for _ in range(20):
            w.mudar_dashboard(1)
        self.assertEqual(w.paginas.count(), 2)
        self.assertEqual(w.paginas.currentIndex(), 0)
        self.assertEqual(w.graficos, graficos)
        w.mudar_dashboard(1)
        self.assertEqual(w.graficos[1].dados["MANHÃ - B"], (0, 0))
        self.assertEqual(w.titulo_dashboard.text(), "Homens e mulheres por turma")

    def test_indicadores_combo_e_graficos_com_alunos_sem_turma(self):
        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta) / "entrada.xlsx"
            criar_entrada_sem_vagas(origem)
            resultado = processar_planilha(origem)
        w = self.janela
        w.mostrar_resultado(resultado)
        self.assertEqual(w.indicadores[0].text(), "403")
        self.assertEqual(w.indicadores[2].text(), "12")
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
        w.mudar_dashboard(1)
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
        self.assertEqual(w.paginas.currentIndex(), 1)
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

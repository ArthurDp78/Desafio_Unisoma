"""Manual externo: caminhos, abertura sem cópia, erros e acesso compacto."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ui.interface_desktop import JanelaPrincipal
from ui.recursos import NOME_MANUAL, caminho_manual


class CaminhoManualTest(unittest.TestCase):
    def test_codigo_fonte_independe_da_pasta_de_trabalho(self):
        pasta_anterior = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as pasta:
                os.chdir(pasta)
                with patch.object(sys, "frozen", False, create=True):
                    self.assertEqual(caminho_manual(), Path(__file__).resolve().parent.parent / NOME_MANUAL)
        finally:
            os.chdir(pasta_anterior)

    def test_pacote_usa_pasta_do_executavel_em_vez_de_internal(self):
        with tempfile.TemporaryDirectory(prefix="ABC Aprendiz ç ") as pasta:
            raiz = Path(pasta).resolve()
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", str(raiz / "ABC_Aprendiz.exe")),
                patch.object(sys, "_MEIPASS", str(raiz / "_internal"), create=True),
            ):
                self.assertEqual(caminho_manual(), raiz / NOME_MANUAL)


class AcessoManualTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.janela = JanelaPrincipal()
        self.janela.show()
        self.app.processEvents()
        self.pasta = tempfile.TemporaryDirectory(prefix="Manual ç ")
        self.addCleanup(self.pasta.cleanup)
        self.pdf = Path(self.pasta.name) / NOME_MANUAL

    def tearDown(self):
        self.janela.close()
        self.janela.deleteLater()
        self.app.processEvents()

    def test_clique_windows_abre_o_pdf_original_sem_alterar_arquivo(self):
        self.pdf.write_bytes(b"%PDF-1.4\nmanual de teste")
        original = self.pdf.read_bytes()
        modificacao = self.pdf.stat().st_mtime_ns
        with (
            patch("ui.interface_desktop.caminho_manual", return_value=self.pdf),
            patch.object(sys, "platform", "win32"),
            patch("ui.interface_desktop.os.startfile", create=True) as abrir,
            patch("ui.interface_desktop.QMessageBox.warning") as aviso,
        ):
            QTest.mouseClick(self.janela.manual, Qt.MouseButton.LeftButton)
            abrir.assert_called_once_with(str(self.pdf))
            aviso.assert_not_called()
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertEqual(self.pdf.stat().st_mtime_ns, modificacao)
        self.assertEqual(list(Path(self.pasta.name).iterdir()), [self.pdf])

    def test_manual_ausente_exibe_mensagem_e_nao_tenta_abrir(self):
        with (
            patch("ui.interface_desktop.caminho_manual", return_value=self.pdf),
            patch("ui.interface_desktop.os.startfile", create=True) as abrir,
            patch("ui.interface_desktop.QDesktopServices.openUrl") as abrir_url,
            patch("ui.interface_desktop.QMessageBox.warning") as aviso,
        ):
            self.janela.manual.click()
            abrir.assert_not_called()
            abrir_url.assert_not_called()
            aviso.assert_called_once_with(
                self.janela, "Manual não encontrado",
                "O Manual do Usuário não foi encontrado na pasta do sistema.",
            )

    def test_falha_no_windows_nao_expoe_detalhes_tecnicos(self):
        self.pdf.touch()
        with (
            patch("ui.interface_desktop.caminho_manual", return_value=self.pdf),
            patch.object(sys, "platform", "win32"),
            patch("ui.interface_desktop.os.startfile", create=True,
                  side_effect=OSError("Detalhe técnico da associação de arquivos")),
            patch("ui.interface_desktop.QMessageBox.warning") as aviso,
        ):
            self.janela.manual.click()
            aviso.assert_called_once_with(
                self.janela, "Não foi possível abrir o manual",
                "Verifique se existe um programa instalado no computador capaz de abrir arquivos PDF.",
            )

    def test_abertura_em_outros_sistemas_e_retorno_de_falha(self):
        self.pdf.touch()
        with (
            patch("ui.interface_desktop.caminho_manual", return_value=self.pdf),
            patch.object(sys, "platform", "linux"),
            patch("ui.interface_desktop.QDesktopServices.openUrl", return_value=True) as abrir,
            patch("ui.interface_desktop.QMessageBox.warning") as aviso,
        ):
            self.janela.manual.click()
            self.assertEqual(abrir.call_args.args[0].toLocalFile(), str(self.pdf))
            aviso.assert_not_called()
            abrir.return_value = False
            self.janela.manual.click()
            self.assertEqual(aviso.call_args.args[1], "Não foi possível abrir o manual")

    def test_cabecalho_compacto_mantem_acesso_e_tooltip(self):
        for largura in (1280, 899, 680, 900, 1280):
            with self.subTest(largura=largura):
                self.janela.resize(largura, 768)
                self.app.processEvents()
                botao = self.janela.manual
                self.assertEqual(botao.toolButtonStyle(),
                                 Qt.ToolButtonStyle.ToolButtonIconOnly if largura < 900
                                 else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                self.assertTrue(botao.isVisible())
                self.assertFalse(botao.icon().isNull())
                self.assertGreaterEqual(botao.width(), 40)
                self.assertGreaterEqual(botao.height(), 40)
                self.assertEqual(botao.toolTip(), "Abrir Manual do Usuário")
                self.assertEqual(botao.accessibleName(), "Manual do usuário")
                limite_direito = botao.mapTo(self.janela, botao.rect().topRight()).x()
                self.assertLess(limite_direito, self.janela.width())


if __name__ == "__main__":
    unittest.main()

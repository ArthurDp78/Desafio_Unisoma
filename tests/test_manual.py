"""Manual do usuário: extração sob demanda, sem sobrescrita, e abertura."""
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
from ui.recursos import NOME_MANUAL, caminho_manual, garantir_manual


class CaminhoManualTest(unittest.TestCase):
    def test_codigo_fonte_independe_da_pasta_de_trabalho(self):
        pasta_anterior = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as pasta:
                try:
                    os.chdir(pasta)
                    with patch.object(sys, "frozen", False, create=True):
                        self.assertEqual(caminho_manual(), Path(__file__).resolve().parent.parent / NOME_MANUAL)
                finally:
                    os.chdir(pasta_anterior)
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


class GarantirManualTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="Manual ç ")
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.destino = self.raiz / "programa" / NOME_MANUAL
        self.origem = self.raiz / "recursos" / NOME_MANUAL
        self.origem.parent.mkdir()
        self.conteudo = b"%PDF-1.4\nmanual empacotado"
        self.origem.write_bytes(self.conteudo)

    def preparar(self):
        return (
            patch("ui.recursos.caminho_manual", return_value=self.destino),
            patch("ui.recursos.caminho_recurso", return_value=self.origem),
        )

    def test_copia_pdf_embutido_quando_esta_ausente(self):
        with self.preparar()[0], self.preparar()[1]:
            resultado = garantir_manual()
        self.assertEqual(resultado, self.destino)
        self.assertEqual(self.destino.read_bytes(), self.conteudo)

    def test_reutiliza_copia_existente_sem_sobrescrever(self):
        self.destino.parent.mkdir(parents=True)
        original = b"%PDF-1.4\ncopia existente"
        self.destino.write_bytes(original)
        modificacao = self.destino.stat().st_mtime_ns
        with patch("ui.recursos.caminho_manual", return_value=self.destino), \
             patch("ui.recursos.caminho_recurso") as recurso:
            resultado = garantir_manual()
            recurso.assert_not_called()
        self.assertEqual(resultado.read_bytes(), original)
        self.assertEqual(resultado.stat().st_mtime_ns, modificacao)

    def test_recurso_ausente_nao_cria_pdf_vazio(self):
        with patch("ui.recursos.caminho_manual", return_value=self.destino), \
             patch("ui.recursos.caminho_recurso", return_value=self.raiz / "inexistente.pdf"):
            with self.assertRaises(FileNotFoundError):
                garantir_manual()
        self.assertFalse(self.destino.exists())

    def test_falha_na_copia_remove_arquivo_parcial(self):
        with patch("ui.recursos.caminho_manual", return_value=self.destino), \
             patch("ui.recursos.caminho_recurso", return_value=self.origem), \
             patch("ui.recursos.shutil.copyfileobj", side_effect=OSError("falha simulada")):
            with self.assertRaises(OSError):
                garantir_manual()
        self.assertFalse(self.destino.exists())


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

    def test_clique_windows_abre_manual_persistente(self):
        self.pdf.write_bytes(b"%PDF-1.4\nmanual de teste")
        original = self.pdf.read_bytes()
        modificacao = self.pdf.stat().st_mtime_ns
        with (
            patch("ui.interface_desktop.garantir_manual", return_value=self.pdf),
            patch.object(sys, "platform", "win32"),
            patch("ui.interface_desktop.os.startfile", create=True) as abrir,
            patch("ui.interface_desktop.QMessageBox.warning") as aviso,
        ):
            QTest.mouseClick(self.janela.manual, Qt.MouseButton.LeftButton)
            abrir.assert_called_once_with(str(self.pdf))
            aviso.assert_not_called()
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertEqual(self.pdf.stat().st_mtime_ns, modificacao)

    def test_recurso_ausente_exibe_aviso_e_nao_tenta_abrir(self):
        with (
            patch("ui.interface_desktop.garantir_manual", side_effect=FileNotFoundError),
            patch("ui.interface_desktop.os.startfile", create=True) as abrir,
            patch("ui.interface_desktop.QDesktopServices.openUrl") as abrir_url,
            patch("ui.interface_desktop.QMessageBox.warning") as aviso,
        ):
            self.janela.manual.click()
            abrir.assert_not_called()
            abrir_url.assert_not_called()
            aviso.assert_called_once_with(
                self.janela, "Manual indisponível",
                "O manual não está disponível neste executável. Gere novamente o pacote da aplicação.",
            )

    def test_falha_ao_criar_copia_pede_permissao_de_gravacao(self):
        with (
            patch("ui.interface_desktop.garantir_manual", side_effect=PermissionError),
            patch("ui.interface_desktop.os.startfile", create=True) as abrir,
            patch("ui.interface_desktop.QMessageBox.warning") as aviso,
        ):
            self.janela.manual.click()
            abrir.assert_not_called()
            aviso.assert_called_once_with(
                self.janela, "Não foi possível preparar o manual",
                "Não foi possível salvar o manual na pasta do programa. Verifique se essa pasta permite gravação.",
            )

    def test_falha_no_windows_nao_expoe_detalhes_tecnicos(self):
        self.pdf.touch()
        with (
            patch("ui.interface_desktop.garantir_manual", return_value=self.pdf),
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
            patch("ui.interface_desktop.garantir_manual", return_value=self.pdf),
            patch.object(sys, "platform", "linux"),
            patch("ui.interface_desktop.QDesktopServices.openUrl", return_value=True) as abrir,
            patch("ui.interface_desktop.QMessageBox.warning") as aviso,
        ):
            self.janela.manual.click()
            self.assertEqual(Path(abrir.call_args.args[0].toLocalFile()), self.pdf)
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

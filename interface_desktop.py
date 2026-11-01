"""Interface Qt desktop: widgets persistentes, model/view e tarefas em background."""
from __future__ import annotations

from math import ceil
from pathlib import Path
import sys

from PySide6.QtCore import QAbstractTableModel, QEasingCurve, QModelIndex, QPropertyAnimation, QPoint, QRect, QRectF, QSortFilterProxyModel, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLayout,
    QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QTableView, QVBoxLayout, QWidget,
)

from apresentacao import (
    ResultadoInterface, exportar_planilha, formatar_percentual, processar_planilha,
    nome_turma_visual, relatorios_interface, separar_ocorrencias,
    texto_busca, texto_diferenca_turmas, texto_variacao_genero,
)

from recursos import caminho_recurso
from relatorio_pdf import IdentificacaoExecucao, exportar_relatorio_pdf
from tema import (
    AZUL, TURQUESA, TURQUESA_ESCURO, TEXTO, TEXTO_SECUNDARIO,
    FUNDO, BRANCO, BORDA, FUNDO_AZUL, ESTILO, ESPACO, MARGEM_PAINEL,
    ICONE, ICONE_CARD, FONTE_GRAFICO, FONTE_EIXO, ALTURA_EIXO,
    ALTURA_GRAFICO_MINIMA, ALTURA_GRAFICO_MAXIMA,
    AJUSTE_MAXIMO_GRAFICOS,
    FUNDO_ALERTA, CONTADOR_MINIMO,
    ESPACO_SECOES, PADDING_ABA_VERTICAL, PADDING_ABA_HORIZONTAL, fonte_interface,
    LIMITE_TURMAS_VARIACAO,
    PADDING_INTERNO,
)

LARGURA_DASHBOARD_DESKTOP = 1200


def icone_widget(nome, tamanho=ICONE):
    widget = QSvgWidget(str(caminho_recurso("assets", "icons", nome + ".svg")))
    widget.setFixedSize(tamanho, tamanho)
    widget.setAccessibleName(nome.replace("_", " "))
    return widget


def fonte_grafico(tamanho=FONTE_GRAFICO, peso=QFont.Weight.Normal):
    return fonte_interface(tamanho, peso)


class ContadorOcorrencias(QLabel):
    """Badge circular que comporta o total sem cortar números com vários dígitos."""

    def __init__(self, parent=None, *, tipo="total"):
        super().__init__(parent)
        self.setObjectName("badgeOcorrencias")
        self.setProperty("tipo", tipo)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.definir(0)

    def definir(self, quantidade):
        self.setText(str(quantidade))
        self.setProperty("vazio", quantidade == 0)
        self.style().unpolish(self)
        self.style().polish(self)
        diametro = max(CONTADOR_MINIMO, self.fontMetrics().horizontalAdvance(self.text()) + 12)
        self.setFixedSize(diametro, diametro)
        self.setAccessibleName(f"{quantidade} ocorrências")

    def paintEvent(self, evento):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        azul = self.property("tipo") == "avisos" or (self.property("tipo") == "total" and self.property("vazio"))
        painter.setBrush(QColor(FUNDO_AZUL if azul else FUNDO_ALERTA))
        painter.drawEllipse(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        painter.end()
        super().paintEvent(evento)


class BotaoNavegacao(QPushButton):
    """Respeita a altura do conteúdo composto, inclusive quando o texto quebra."""

    def sizeHint(self):
        return self.layout().sizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()


class NavegacaoSecoes(QFrame):
    """A única animação move um marcador de 3 px, sem mover os painéis."""
    secao_alterada = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("navegacao")
        self.indice = 0
        self.botoes = []
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 10)
        layout.setSpacing(5)
        self.rotulos = []
        for indice, (titulo, icone, secao) in enumerate((
            ("Dashboard", "tab_dashboard", "dashboard"),
            ("Alunos por turma", "tab_alunos", "alunos"),
            ("Inconsistências e avisos", "tab_inconsistencias", "ocorrencias"),
        )):
            botao = BotaoNavegacao()
            botao.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            botao.setObjectName("navegacaoBotao")
            botao.setProperty("secao", secao)
            botao.setMinimumHeight(max(ICONE, CONTADOR_MINIMO) + 2 * PADDING_ABA_VERTICAL)
            conteudo = QHBoxLayout(botao)
            conteudo.setContentsMargins(PADDING_ABA_HORIZONTAL, PADDING_ABA_VERTICAL,
                                       PADDING_ABA_HORIZONTAL, PADDING_ABA_VERTICAL)
            conteudo.setSpacing(8)
            conteudo.addStretch()
            imagem = icone_widget(icone)
            imagem.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            conteudo.addWidget(imagem)
            rotulo = QLabel(titulo)
            rotulo.setObjectName("textoNavegacao")
            rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            conteudo.addWidget(rotulo)
            self.rotulos.append(rotulo)
            if indice == 2:
                # Reserva discreta evita deslocar o título quando o total passa de zero.
                espaco_badge = QWidget()
                espaco_badge.setMinimumSize(CONTADOR_MINIMO, CONTADOR_MINIMO)
                espaco_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                layout_badge = QHBoxLayout(espaco_badge)
                layout_badge.setContentsMargins(0, 0, 0, 0)
                self.badge = ContadorOcorrencias(espaco_badge)
                self.badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                self.badge.hide()
                layout_badge.addWidget(self.badge)
                conteudo.addWidget(espaco_badge)
            conteudo.addStretch()
            botao.setCheckable(True)
            botao.setAccessibleName(titulo)
            botao.setToolTip(titulo)
            self.grupo.addButton(botao, indice)
            self.botoes.append(botao)
            layout.addWidget(botao, 1)
        self.botoes[0].setChecked(True)
        self.grupo.idClicked.connect(self.selecionar)
        self.marcador = QFrame(self)
        self.marcador.setObjectName("marcador")
        self.marcador.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.animacao = QPropertyAnimation(self.marcador, b"geometry", self)
        self.animacao.setDuration(120)
        self.animacao.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._atualizar_estilo()

    def selecionar(self, indice):
        if not 0 <= indice < len(self.botoes) or indice == self.indice:
            return
        self.indice = indice
        self.botoes[indice].setChecked(True)
        self._atualizar_estilo()
        self._posicionar(animar=True)
        self.secao_alterada.emit(indice)

    def _atualizar_estilo(self):
        for indice, rotulo in enumerate(self.rotulos):
            rotulo.setProperty("ativa", indice == self.indice)
            rotulo.style().unpolish(rotulo)
            rotulo.style().polish(rotulo)
        self.marcador.setProperty("secao", self.botoes[self.indice].property("secao"))
        self.marcador.style().unpolish(self.marcador)
        self.marcador.style().polish(self.marcador)
        self.marcador.update()

    def atualizar_ocorrencias(self, inconsistencias=0, avisos=0):
        total = inconsistencias + avisos
        self.badge.definir(total)
        self.badge.setVisible(total > 0)
        descricao = f"{inconsistencias} inconsistências e {avisos} avisos; {total} ocorrências"
        self.badge.setAccessibleName(descricao)
        self.botoes[2].setAccessibleName(f"Inconsistências e avisos: {descricao}")
        self.botoes[2].setToolTip(descricao)

    def _posicionar(self, animar=False):
        botao = self.botoes[self.indice]
        destino = QRect(botao.x() + 12, self.height() - 6, max(1, botao.width() - 24), 3)
        self.animacao.stop()
        if animar and self.isVisible():
            self.animacao.setStartValue(self.marcador.geometry())
            self.animacao.setEndValue(destino)
            self.animacao.start()
        else:
            self.marcador.setGeometry(destino)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.layout().activate()
        self._posicionar()

    def showEvent(self, evento):
        super().showEvent(evento)
        self.layout().activate()
        self._posicionar()


class RelatorioOcorrencias(QPlainTextEdit):
    """Relatório selecionável que cresce com as linhas; a página cuida do scroll."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("textoOcorrencias")
        self.setReadOnly(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(0)
        self._blocos_divisoria = []
        self._ajustando = False
        self._ajuste_altura = QTimer(self)
        self._ajuste_altura.setSingleShot(True)
        self._ajuste_altura.timeout.connect(self._ajustar_altura)
        self.document().documentLayout().documentSizeChanged.connect(self._agendar_altura)
        self.textChanged.connect(self._agendar_altura)
        self._agendar_altura()

    def _agendar_altura(self, *_):
        if not self._ajustando:
            self._ajuste_altura.start(0)

    def _ajustar_altura(self):
        self._ajustando = True
        try:
            documento = self.document()
            layout = documento.documentLayout()
            bloco = documento.begin()
            altura = 0
            encontrou_registro = False
            self._blocos_divisoria = []
            while bloco.isValid():
                # Identifica os cabeçalhos do relatório existente, sem mudar seu texto.
                if " · Aba Alunos · Linha(s) " in bloco.text():
                    if encontrou_registro:
                        espaco = bloco.previous()
                        while espaco.isValid() and espaco.text().strip():
                            espaco = espaco.previous()
                        if espaco.isValid():
                            self._blocos_divisoria.append(espaco)
                    encontrou_registro = True
                # blockBoundingRect força o layout também das linhas fora do viewport.
                altura += layout.blockBoundingRect(bloco).height()
                bloco = bloco.next()
            altura = ceil(altura + 2 * documento.documentMargin() + 2 * self.frameWidth()) + 2
            if altura != self.minimumHeight() or altura != self.maximumHeight():
                self.setFixedHeight(altura)
            self.viewport().update()
        finally:
            self._ajustando = False

    def paintEvent(self, evento):
        super().paintEvent(evento)
        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor(BORDA), 1))
        for bloco in self._blocos_divisoria:
            if bloco.isValid():
                area = self.blockBoundingGeometry(bloco).translated(self.contentOffset())
                y = round(area.center().y())
                if evento.rect().top() <= y <= evento.rect().bottom():
                    painter.drawLine(0, y, self.viewport().width() - 1, y)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if evento.size().width() != evento.oldSize().width():
            self._agendar_altura()

    def showEvent(self, evento):
        super().showEvent(evento)
        self._agendar_altura()


class ModeloAlunos(QAbstractTableModel):
    cabecalhos = ("Nome", "Sexo", "Disponibilidade")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.registros = []

    def definir(self, registros):
        self.beginResetModel()
        self.registros = registros
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.registros)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.cabecalhos)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            valor = self.registros[index.row()][self.cabecalhos[index.column()]]
            return {"M": "Masculino", "F": "Feminino"}.get(valor, valor) if index.column() == 1 else valor
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.cabecalhos[section] if orientation == Qt.Orientation.Horizontal else section + 1
        return None


class FiltroAlunos(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.consulta = ""
        self.sexo = ""
        self.disponibilidade = ""

    def pesquisar(self, texto):
        self.consulta = texto_busca(texto.strip())
        self.invalidate()

    def filtrar(self, sexo, disponibilidade):
        self.sexo = sexo
        self.disponibilidade = texto_busca(disponibilidade)
        self.invalidate()

    def filterAcceptsRow(self, linha, parent):
        registro = self.sourceModel().registros[linha]
        return (self.consulta in texto_busca(registro["Nome"])
                and (not self.sexo or registro["Sexo"] == self.sexo)
                and (not self.disponibilidade
                     or texto_busca(registro["Disponibilidade"]) == self.disponibilidade))


class Tarefa(QThread):
    concluida = Signal(object)
    falhou = Signal(str)

    def __init__(self, funcao, *args, parent=None):
        super().__init__(parent)
        self.funcao = funcao
        self.args = args

    def run(self):
        try:
            self.concluida.emit(self.funcao(*self.args))
        except Exception as erro:
            self.falhou.emit(str(erro))


class GradeResponsiva(QWidget):
    """Reposiciona os mesmos widgets conforme a largura, sem recriá-los."""

    def __init__(self, widgets, largura_coluna, opcoes=(2, 1)):
        super().__init__()
        self.widgets = widgets
        self.largura_coluna = largura_coluna
        self.opcoes = opcoes
        self.colunas = 0
        self.colunas_fixas = None
        self.grade = QGridLayout(self)
        self.grade.setContentsMargins(0, 0, 0, 0)
        self.grade.setSpacing(12)
        self.grade.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self._organizar()

    def _organizar(self):
        colunas = self.colunas_fixas or next(
            (n for n in self.opcoes if self.width() >= n * self.largura_coluna + (n - 1) * 12), 1
        )
        if colunas == self.colunas:
            return
        while self.grade.count():
            self.grade.takeAt(0)
        for coluna in range(max(self.opcoes)):
            self.grade.setColumnStretch(coluna, int(coluna < colunas))
        for indice, widget in enumerate(self.widgets):
            self.grade.addWidget(widget, indice // colunas, indice % colunas)
        self.colunas = colunas
        self.updateGeometry()

    def definir_colunas(self, colunas):
        """Permite coordenar várias grades com o mesmo modo da janela."""
        self.colunas_fixas = colunas
        self._organizar()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._organizar()


class Grafico(QWidget):
    """Barras roláveis; a escala é compartilhada com o eixo fixo irmão."""
    turma_clicada = Signal(str)
    visual_alterado = Signal()

    def __init__(self, por_sexo=False, parent=None):
        super().__init__(parent)
        self.por_sexo = por_sexo
        self.altura_minima_linha = 52 if por_sexo else 44
        self.dados, self.capacidades = {}, {}
        self.selecionada = ""
        self.areas = []
        self.setAccessibleName("Homens e mulheres por turma" if por_sexo else "Número de alunos por turma")
        self.setMinimumHeight(160)

    def definir(self, dados, capacidades=None):
        self.dados = dados
        self.capacidades = capacidades or {}
        self.setMinimumHeight(max(160, len(dados) * self.altura_minima_linha))
        self.update()
        self.visual_alterado.emit()

    def selecionar(self, turma):
        if turma != self.selecionada:
            self.selecionada = turma
            self.update()

    def escala(self, largura=None):
        """Geometria e escala de desenho, sem calcular métricas da solução."""
        fm = QFontMetrics(fonte_grafico())
        esquerda = max((fm.horizontalAdvance(nome) for nome in self.dados), default=90) + 22
        direita = max(esquerda + 40, (self.width() if largura is None else largura) - (62 if self.por_sexo else 110))
        valores = [v for par in self.dados.values() for v in par] if self.por_sexo else list(self.dados.values())
        passo = max(1, ceil(max(valores + list(self.capacidades.values()), default=0) / 4))
        return esquerda, direita, passo, passo * 4

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.visual_alterado.emit()

    def paintEvent(self, evento):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(BRANCO))
        painter.setFont(fonte_grafico())
        self.areas = []
        if not self.dados:
            painter.setPen(QColor(TEXTO_SECUNDARIO))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sem distribuição.")
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        esquerda, direita, passo, maximo = self.escala()
        largura = direita - esquerda
        altura_linha = max(self.altura_minima_linha, min(80, self.height() / len(self.dados)))
        for i in range(5):
            x = esquerda + largura * i / 4
            painter.setPen(QPen(QColor(BORDA if i else AZUL), 1.0 if i else 1.3))
            painter.drawLine(int(x), 0, int(x), self.height())
        for i, (nome, valor) in enumerate(self.dados.items()):
            y = i * altura_linha
            area = QRectF(0, y, self.width(), altura_linha)
            self.areas.append((area, nome))
            if nome == self.selecionada:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(FUNDO_AZUL))
                painter.drawRoundedRect(QRectF(0, y + 3, esquerda - 10, altura_linha - 6), 7, 7)
            painter.setPen(QColor(TEXTO))
            painter.drawText(QRectF(8, y, esquerda - 20, altura_linha), Qt.AlignmentFlag.AlignVCenter, nome)
            barras = ((valor[0], AZUL), (valor[1], TURQUESA)) if self.por_sexo else (
                (valor, AZUL if nome.startswith("MANHÃ") else TURQUESA_ESCURO),
            )
            if not self.por_sexo and nome in self.capacidades:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(FUNDO_AZUL))
                painter.drawRoundedRect(QRectF(esquerda, y + altura_linha / 2 - 11,
                                              self.capacidades[nome] / maximo * largura, 22), 4, 4)
            for j, (quantidade, cor) in enumerate(barras):
                altura = 18 if self.por_sexo else 22
                topo = y + altura_linha / 2 - (22 if self.por_sexo else 11) + j * 26
                tamanho = quantidade / maximo * largura
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(cor))
                if quantidade:
                    painter.drawRoundedRect(QRectF(esquerda, topo, tamanho, altura), 4, 4)
                painter.setPen(QColor(TEXTO))
                rotulo = f"{quantidade} / {self.capacidades[nome]}" if nome in self.capacidades else str(quantidade)
                x_rotulo = esquerda + tamanho + 9 if self.por_sexo else direita + 10
                painter.drawText(QRectF(x_rotulo, topo - 3, 96 if not self.por_sexo else 50, altura + 6),
                                 Qt.AlignmentFlag.AlignVCenter, rotulo)

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            for area, turma in self.areas:
                if area.contains(evento.position()):
                    self.turma_clicada.emit(turma)
                    break
        super().mousePressEvent(evento)


class EixoHorizontal(QWidget):
    """Ticks, linha e unidade fora do QScrollArea: não rolam com as barras."""

    def __init__(self, grafico, area, parent=None):
        super().__init__(parent)
        self.grafico, self.area = grafico, area
        self.titulo = "Quantidade de alunos"
        self.setFixedHeight(ALTURA_EIXO)
        self.setAccessibleName(self.titulo)
        grafico.visual_alterado.connect(self.update)
        area.verticalScrollBar().rangeChanged.connect(lambda *_: self.update())

    def paintEvent(self, evento):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(BRANCO))
        if not self.grafico.dados:
            return
        origem = self.mapFromGlobal(self.area.viewport().mapToGlobal(QPoint(0, 0))).x()
        esquerda, direita, passo, _ = self.grafico.escala(self.area.viewport().width())
        esquerda, direita = esquerda + origem, direita + origem
        painter.setFont(fonte_grafico())
        painter.setPen(QPen(QColor(AZUL), 1.3))
        painter.drawLine(int(esquerda), 2, int(direita), 2)
        for indice in range(5):
            x = esquerda + (direita - esquerda) * indice / 4
            painter.drawLine(int(x), 2, int(x), 7)
            painter.setPen(QColor(TEXTO))
            painter.drawText(QRectF(x - 30, 11, 60, 21), Qt.AlignmentFlag.AlignCenter, str(indice * passo))
        painter.setFont(fonte_grafico(FONTE_EIXO, QFont.Weight.Medium))
        painter.setPen(QColor(TEXTO))
        painter.drawText(QRectF(esquerda, 36, direita - esquerda, 25), Qt.AlignmentFlag.AlignCenter, self.titulo)


class JanelaPrincipal(QMainWindow):
    def __init__(self, processador=processar_planilha, exportador=exportar_planilha):
        super().__init__()
        self.processador = processador
        self.exportador = exportador
        self.exportador_pdf = exportar_relatorio_pdf
        self.arquivo = None
        self.resultado = None
        self.execucao_relatorio = None
        self.modo_acoes_arquivo = None
        self._tarefa = None
        self._ocupado = False
        self.modo_dashboard = None
        self.indice_dashboard = 0
        self._ajuste_dashboard = QTimer(self)
        self._ajuste_dashboard.setSingleShot(True)
        self._ajuste_dashboard.timeout.connect(self._ajustar_excesso_dashboard)
        self.setWindowTitle("ABC Aprendiz - Ensalamento")
        self.setWindowIcon(QIcon(str(caminho_recurso("assets", "logo_abc_aprendiz.png"))))
        self.resize(LARGURA_DASHBOARD_DESKTOP + 80, 880)
        self.setMinimumSize(680, 600)
        self.setStyleSheet(ESTILO)
        self._montar()
        self._atualizar_modo_dashboard()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if hasattr(self, "grade_resumos"):
            self._atualizar_modo_dashboard()

    def _atualizar_modo_dashboard(self):
        self._organizar_acoes_arquivo()
        novo_modo = "desktop" if self.width() >= LARGURA_DASHBOARD_DESKTOP else "compacto"
        if novo_modo != self.modo_dashboard:
            self.modo_dashboard = novo_modo
            self.reorganizar_dashboard()
        colunas = 4 if novo_modo == "desktop" else 2
        if colunas != self.grade_indicadores.colunas:
            self.grade_indicadores.definir_colunas(colunas)
        altura = max(ALTURA_GRAFICO_MINIMA, min(ALTURA_GRAFICO_MAXIMA, int(self.height() * 0.48)))
        for painel in self.grade_graficos.widgets:
            if painel.minimumHeight() != altura:
                painel.setMinimumHeight(altura)
        self.grade_graficos.setMaximumHeight(altura)
        self.grade_graficos.updateGeometry()
        self._ajuste_dashboard.start(0)

    def _organizar_acoes_arquivo(self):
        compacto = self.width() < 900
        if compacto == self.modo_acoes_arquivo:
            return
        self.modo_acoes_arquivo = compacto
        grade = self.acoes_arquivo
        while grade.count():
            grade.takeAt(0)
        for coluna in range(5):
            grade.setColumnStretch(coluna, 0)
        if compacto:
            grade.addWidget(self.importar, 0, 0)
            grade.addWidget(self.nome_arquivo, 0, 1, 1, 2)
            for coluna, botao in enumerate((self.gerar, self.exportar, self.exportar_pdf)):
                grade.addWidget(botao, 1, coluna)
                grade.setColumnStretch(coluna, 1)
        else:
            for coluna, widget in enumerate((self.importar, self.nome_arquivo, self.gerar, self.exportar, self.exportar_pdf)):
                grade.addWidget(widget, 0, coluna)
            grade.setColumnStretch(1, 1)

    def _ajustar_excesso_dashboard(self):
        """Cede apenas poucos pixels dos gráficos quando isso elimina o scroll externo."""
        if self.modo_dashboard != "desktop" or not self.dashboard.isVisible():
            return
        layout = self.dashboard.widget().layout()
        layout.activate()
        altura_atual = self.grade_graficos.minimumSizeHint().height()
        altura_outros = layout.minimumSize().height() - altura_atual
        disponivel = self.dashboard.viewport().height() - altura_outros
        preferida = max(ALTURA_GRAFICO_MINIMA, min(ALTURA_GRAFICO_MAXIMA, int(self.height() * 0.48)))
        excesso = preferida - disponivel
        altura = disponivel if (0 < excesso <= AJUSTE_MAXIMO_GRAFICOS
                                 and disponivel >= ALTURA_GRAFICO_MINIMA) else preferida
        if altura != altura_atual:
            for painel in self.grade_graficos.widgets:
                painel.setMinimumHeight(altura)
            self.grade_graficos.setMaximumHeight(altura)
            self.grade_graficos.updateGeometry()
            self._ajuste_dashboard.start(0)

    def reorganizar_dashboard(self):
        """Só cruza os modos; mantém widgets, dados, sinais e seleção existentes."""
        desktop = self.modo_dashboard == "desktop"
        self.controles_dashboard.setVisible(not desktop)
        self.grade_graficos.definir_colunas(2 if desktop else 1)
        self.grade_resumos.definir_colunas(2 if desktop else 1)
        self._atualizar_pagina_dashboard()

    def _atualizar_pagina_dashboard(self):
        for indice, painel in enumerate(self.grade_graficos.widgets):
            painel.setVisible(self.modo_dashboard == "desktop" or indice == self.indice_dashboard)
        self.pagina_dashboard.setText(f"{self.indice_dashboard + 1} / {len(self.graficos)}")

    def mudar_dashboard(self, passo):
        if self.modo_dashboard == "compacto":
            self.indice_dashboard = (self.indice_dashboard + passo) % len(self.graficos)
            self._atualizar_pagina_dashboard()

    @staticmethod
    def _rotulo(texto, tipo="discreto"):
        rotulo = QLabel(texto)
        rotulo.setObjectName(tipo)
        return rotulo

    @staticmethod
    def _painel():
        frame = QFrame()
        frame.setObjectName("painel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(MARGEM_PAINEL, 12, MARGEM_PAINEL, 12)
        layout.setSpacing(8)
        return frame, layout

    def _titulo_painel(self, layout, texto, icone):
        linha = QHBoxLayout()
        linha.setSpacing(8)
        linha.addWidget(icone_widget(icone))
        rotulo = self._rotulo(texto, "secao")
        rotulo.setWordWrap(True)
        linha.addWidget(rotulo, 1)
        layout.addLayout(linha)

    def _montar(self):
        central = QWidget()
        central.setObjectName("central")
        # Em telas com escala alta, o conteúdo mantém seus mínimos legíveis;
        # a janela ganha rolagem externa em vez de esmagar a tabela.
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)
        rolagem.setWidget(central)
        self.setCentralWidget(rolagem)
        principal = QVBoxLayout(central)
        principal.setContentsMargins(22, 17, 22, 15)
        principal.setSpacing(13)
        cabecalho = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(str(caminho_recurso("assets", "logo_abc_aprendiz.png"))).scaledToHeight(
            42, Qt.TransformationMode.SmoothTransformation))
        logo.setAccessibleName("ABC Aprendiz")
        cabecalho.addWidget(logo)
        cabecalho.addStretch()
        cabecalho.addWidget(self._rotulo("Sistema de Ensalamento", "titulo"))
        principal.addLayout(cabecalho)
        arquivo, linha_arquivo = self._painel()
        self.acoes_arquivo = QGridLayout()
        self.importar = QPushButton("Importar XLSX…")
        self.importar.clicked.connect(self.escolher_arquivo)
        self.nome_arquivo = self._rotulo("Nenhuma planilha selecionada")
        self.nome_arquivo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.gerar = QPushButton("Gerar distribuição")
        self.gerar.setObjectName("primario")
        self.gerar.setEnabled(False)
        self.gerar.clicked.connect(self.gerar_distribuicao)
        self.exportar = QPushButton("Exportar XLSX…")
        self.exportar.setObjectName("exportar")
        self.exportar.setEnabled(False)
        self.exportar.clicked.connect(self.escolher_destino)
        self.exportar_pdf = QPushButton("Exportar relatório PDF")
        self.exportar_pdf.setObjectName("exportar")
        self.exportar_pdf.setToolTip("Salvar o relatório completo, incluindo todos os alunos por turma")
        self.exportar_pdf.setEnabled(False)
        self.exportar_pdf.clicked.connect(self.escolher_destino_pdf)
        linha_arquivo.addLayout(self.acoes_arquivo)
        self._organizar_acoes_arquivo()
        principal.addWidget(arquivo)
        self.carregamento = QWidget()
        linha_carregamento = QVBoxLayout(self.carregamento)
        linha_carregamento.setContentsMargins(0, 0, 0, 0)
        linha_carregamento.setSpacing(6)
        self.mensagem_carregamento = self._rotulo("Aguarde. A distribuição está sendo gerada.")
        self.mensagem_carregamento.setWordWrap(True)
        linha_carregamento.addWidget(self.mensagem_carregamento)
        self.progresso = QProgressBar()
        self.progresso.setRange(0, 0)
        self.progresso.setTextVisible(False)
        self.progresso.setFixedHeight(4)
        linha_carregamento.addWidget(self.progresso)
        self.carregamento.hide()
        principal.addWidget(self.carregamento)
        self.banner_erro = QFrame()
        self.banner_erro.setObjectName("bannerErro")
        linha_erro = QHBoxLayout(self.banner_erro)
        linha_erro.setContentsMargins(MARGEM_PAINEL, 12, MARGEM_PAINEL, 12)
        linha_erro.setSpacing(10)
        linha_erro.addWidget(icone_widget("tab_inconsistencias"), 0, Qt.AlignmentFlag.AlignTop)
        textos_erro = QVBoxLayout()
        textos_erro.setSpacing(4)
        self.titulo_erro = self._rotulo("Não foi possível processar a planilha.", "subtitulo")
        self.orientacao_erro = self._rotulo("Verifique se o arquivo está no formato esperado pelo sistema.")
        self.detalhe_erro = self._rotulo("")
        for rotulo in (self.titulo_erro, self.orientacao_erro, self.detalhe_erro):
            rotulo.setWordWrap(True)
            rotulo.setTextFormat(Qt.TextFormat.PlainText)
            rotulo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            textos_erro.addWidget(rotulo)
        self.detalhe_erro.hide()
        linha_erro.addLayout(textos_erro, 1)
        self.banner_erro.hide()
        principal.addWidget(self.banner_erro)
        self.navegacao = NavegacaoSecoes()
        principal.addWidget(self.navegacao)
        self.secoes = QStackedWidget()
        self.secoes.setAccessibleName("Seção principal")
        self.navegacao.secao_alterada.connect(self.secoes.setCurrentIndex)
        self.navegacao.secao_alterada.connect(lambda _: self._ajuste_dashboard.start(0))
        self.secoes.addWidget(self._montar_dashboard())
        alunos, layout_alunos = self._painel()
        alunos.setMinimumSize(360, 200)
        layout_alunos.addWidget(self._rotulo("Alunos por turma", "secao"))
        navegacao_turma = QWidget()
        linha_turma = QHBoxLayout(navegacao_turma)
        linha_turma.setContentsMargins(0, 0, 0, 0)
        linha_turma.setSpacing(6)
        self.turma_anterior = QPushButton()
        self.turma_anterior.setIcon(QIcon(str(caminho_recurso("assets", "icons", "chevron_left.svg"))))
        self.turma_anterior.setAccessibleName("Turma anterior")
        self.turma_anterior.setToolTip("Turma anterior")
        self.turma_anterior.clicked.connect(lambda: self.mudar_turma(-1))
        self.turma_proxima = QPushButton()
        self.turma_proxima.setIcon(QIcon(str(caminho_recurso("assets", "icons", "chevron_right.svg"))))
        self.turma_proxima.setAccessibleName("Próxima turma")
        self.turma_proxima.setToolTip("Próxima turma")
        self.turma_proxima.clicked.connect(lambda: self.mudar_turma(1))
        self.turma = QComboBox()
        self.turma.setObjectName("seletorTurma")
        self.turma.setAccessibleName("Turma exibida")
        self.turma.setMinimumWidth(160)
        self.turma.currentTextChanged.connect(self.mostrar_turma)
        linha_turma.addWidget(self.turma_anterior)
        linha_turma.addWidget(self.turma, 1)
        linha_turma.addWidget(self.turma_proxima)
        self.busca = QLineEdit()
        self.busca.setObjectName("buscaAlunos")
        self.busca.setPlaceholderText("Buscar nome nesta turma")
        self.busca.setAccessibleName("Buscar aluno nesta turma")
        self.busca.setClearButtonEnabled(True)
        self.filtro_sexo = QComboBox()
        self.filtro_sexo.setObjectName("filtroSexo")
        self.filtro_sexo.setAccessibleName("Filtrar por sexo")
        for texto, valor in (("Todos", ""), ("Feminino", "F"), ("Masculino", "M")):
            self.filtro_sexo.addItem(texto, valor)
        self.filtro_disponibilidade = QComboBox()
        self.filtro_disponibilidade.setObjectName("filtroDisponibilidade")
        self.filtro_disponibilidade.setAccessibleName("Filtrar por disponibilidade")
        for texto, valor in (("Todas", ""), ("Manhã", "Manhã"), ("Tarde", "Tarde")):
            self.filtro_disponibilidade.addItem(texto, valor)
        campos = []
        for titulo, controle in (("Turma", navegacao_turma), ("Buscar por nome", self.busca),
                                 ("Sexo", self.filtro_sexo), ("Disponibilidade", self.filtro_disponibilidade)):
            campo = QWidget()
            caixa_campo = QVBoxLayout(campo)
            caixa_campo.setContentsMargins(0, 0, 0, 0)
            caixa_campo.setSpacing(4)
            caixa_campo.addWidget(self._rotulo(titulo))
            caixa_campo.addWidget(controle)
            campos.append(campo)
        self.controles_alunos = GradeResponsiva(campos, 260, (4, 2, 1))
        layout_alunos.addWidget(self.controles_alunos)
        self.modelo = ModeloAlunos(self)
        self.filtro = FiltroAlunos(self)
        self.filtro.setSourceModel(self.modelo)
        self.busca.textChanged.connect(self.filtro.pesquisar)
        self.busca.textChanged.connect(self.atualizar_contagem)
        self.filtro_sexo.currentIndexChanged.connect(self.atualizar_filtros)
        self.filtro_disponibilidade.currentIndexChanged.connect(self.atualizar_filtros)
        self.filtro.rowsInserted.connect(self.atualizar_contagem)
        self.filtro.rowsRemoved.connect(self.atualizar_contagem)
        self.filtro.modelReset.connect(self.atualizar_contagem)
        self.tabela = QTableView()
        self.tabela.setAccessibleName("Alunos da turma selecionada")
        self.tabela.setModel(self.filtro)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tabela.setShowGrid(False)
        self.tabela.setWordWrap(False)
        self.tabela.setMinimumHeight(150)
        self.tabela.verticalHeader().setDefaultSectionSize(33)
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabela.setColumnWidth(1, 95)
        self.tabela.setColumnWidth(2, 125)
        layout_alunos.addWidget(self.tabela, 1)
        self.contagem = self._rotulo("Sem distribuição.")
        layout_alunos.addWidget(self.contagem)
        self.secoes.addWidget(alunos)
        self.ocorrencias = QScrollArea()
        self.ocorrencias.setWidgetResizable(True)
        self.ocorrencias.setFrameShape(QFrame.Shape.NoFrame)
        self.ocorrencias.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ocorrencias.setAccessibleName("Inconsistências e avisos com rolagem vertical")
        conteudo_ocorrencias = QWidget()
        conteudo_ocorrencias.setObjectName("central")
        layout_ocorrencias = QVBoxLayout(conteudo_ocorrencias)
        layout_ocorrencias.setContentsMargins(0, 0, 4, 0)
        layout_ocorrencias.setSpacing(ESPACO_SECOES)
        self.contadores_ocorrencias = []
        self.paineis_ocorrencias = []
        editores = []
        for titulo, icone, descricao in (
            ("Inconsistências", "tab_inconsistencias",
             "Registros que não entraram no ensalamento e precisam de revisão manual."),
            ("Avisos", "tab_avisos",
             "Normalizações automáticas e registros mantidos válidos, sem bloqueio cadastral."),
        ):
            painel, caixa = self._painel()
            painel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            linha = QHBoxLayout()
            linha.setSpacing(8)
            linha.addWidget(icone_widget(icone))
            linha.addWidget(self._rotulo(titulo, "secao"), 1)
            contador = ContadorOcorrencias(tipo="avisos" if titulo == "Avisos" else "inconsistencias")
            linha.addWidget(contador)
            self.contadores_ocorrencias.append(contador)
            caixa.addLayout(linha)
            explicacao = self._rotulo(descricao)
            explicacao.setWordWrap(True)
            caixa.addWidget(explicacao)
            editor = RelatorioOcorrencias()
            editor.setProperty("vazio", True)
            editor.setAccessibleName(f"Relatório agrupado de {titulo.lower()}")
            editor.setPlainText("Nenhuma instância avaliada.")
            caixa.addWidget(editor)
            editores.append(editor)
            self.paineis_ocorrencias.append(painel)
            layout_ocorrencias.addWidget(painel)
        layout_ocorrencias.addStretch(1)
        self.ocorrencias.setWidget(conteudo_ocorrencias)
        self.relatorio, self.avisos = editores
        self.secoes.addWidget(self.ocorrencias)
        # O tamanho preferido dos editores não deve forçar rolagem da janela inteira.
        # A área principal cresce com a janela e cada conteúdo preserva seu mínimo legível.
        self.secoes.setMinimumHeight(self.secoes.minimumSizeHint().height())
        self.secoes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        principal.addWidget(self.secoes, 1)
        self._atualizar_botoes()

    def _montar_dashboard(self):
        self.dashboard = QScrollArea()
        self.dashboard.setWidgetResizable(True)
        self.dashboard.setFrameShape(QFrame.Shape.NoFrame)
        self.dashboard.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dashboard.setAccessibleName("Painel de gestão com rolagem vertical")
        conteudo = QWidget()
        conteudo.setObjectName("central")
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(ESPACO)
        cards = []
        self.indicadores, self.detalhes_indicadores = [], []
        for titulo, icone, tipo in (
            ("Alunos alocados", "card_alocados", "positivo"),
            ("Alunos sem turma", "card_sem_turma", "azul"),
            ("Ocupação", "chart_ocupacao", "turquesa"),
            ("Ociosidade", "card_resumo_turno", "azul"),
        ):
            frame = QFrame()
            frame.setObjectName("cardResumo")
            caixa = QHBoxLayout(frame)
            caixa.setContentsMargins(MARGEM_PAINEL, 12, MARGEM_PAINEL, 12)
            caixa.setSpacing(ESPACO)
            container = QFrame()
            container.setObjectName("iconeCard")
            container.setProperty("tipo", tipo)
            icones = QVBoxLayout(container)
            icones.setContentsMargins(10, 10, 10, 10)
            icones.addWidget(icone_widget(icone, ICONE_CARD))
            caixa.addWidget(container, 0, Qt.AlignmentFlag.AlignVCenter)
            textos = QVBoxLayout()
            textos.setSpacing(2)
            legenda = self._rotulo(titulo)
            textos.addWidget(legenda)
            numero = self._rotulo("—", "numeroCard")
            textos.addWidget(numero)
            detalhe = self._rotulo("")
            textos.addWidget(detalhe)
            caixa.addLayout(textos, 1)
            self.indicadores.append(numero)
            self.detalhes_indicadores.append(detalhe)
            cards.append(frame)
        self.grade_indicadores = GradeResponsiva(cards, 230, (4, 2, 1))
        layout.addWidget(self.grade_indicadores)

        self.graficos = [Grafico(), Grafico(por_sexo=True)]
        self.areas_graficos, self.eixos_graficos = [], []
        self.controles_dashboard = QWidget()
        navegacao = QHBoxLayout(self.controles_dashboard)
        navegacao.setContentsMargins(0, 0, 0, 0)
        navegacao.addStretch()
        self.dashboard_anterior = QPushButton("‹")
        self.dashboard_anterior.setAccessibleName("Gráfico anterior")
        self.dashboard_anterior.clicked.connect(lambda: self.mudar_dashboard(-1))
        self.pagina_dashboard = self._rotulo("1 / 2")
        self.pagina_dashboard.setAccessibleName("Página dos gráficos")
        self.dashboard_proximo = QPushButton("›")
        self.dashboard_proximo.setAccessibleName("Próximo gráfico")
        self.dashboard_proximo.clicked.connect(lambda: self.mudar_dashboard(1))
        navegacao.addWidget(self.dashboard_anterior)
        navegacao.addWidget(self.pagina_dashboard)
        navegacao.addWidget(self.dashboard_proximo)
        layout.addWidget(self.controles_dashboard)
        paineis = []
        for grafico, titulo, icone, legenda in zip(
            self.graficos, ("Alunos por turma", "Homens e mulheres por turma"),
            ("chart_ocupacao", "chart_genero"),
            ("Azul: manhã · Turquesa: tarde · Alunos / capacidade", "Azul: homens · Turquesa: mulheres"),
        ):
            painel, caixa = self._painel()
            self._titulo_painel(caixa, titulo, icone)
            rotulo = self._rotulo(legenda, "legenda")
            rotulo.setWordWrap(True)
            caixa.addWidget(rotulo)
            caixa.addWidget(self._rotulo("Turma", "eixo"))
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setWidget(grafico)
            self.areas_graficos.append(area)
            caixa.addWidget(area, 1)
            eixo = EixoHorizontal(grafico, area)
            caixa.addWidget(eixo)
            self.eixos_graficos.append(eixo)
            grafico.turma_clicada.connect(self.ir_para_turma)
            paineis.append(painel)
        self.grade_graficos = GradeResponsiva(paineis, 480)
        layout.addWidget(self.grade_graficos)

        qualidade, caixa = self._painel()
        self._titulo_painel(caixa, "Qualidade da distribuição", "card_qualidade")
        equilibrio = QFrame()
        equilibrio.setObjectName("quadroQualidade")
        area_equilibrio = QVBoxLayout(equilibrio)
        area_equilibrio.setContentsMargins(PADDING_INTERNO, PADDING_INTERNO, PADDING_INTERNO, PADDING_INTERNO)
        area_equilibrio.setSpacing(6)
        area_equilibrio.addWidget(self._rotulo("Equilíbrio entre turmas", "subtitulo"))
        explicacao = self._rotulo("Maior diferença de tamanho no mesmo turno.")
        explicacao.setWordWrap(True)
        area_equilibrio.addWidget(explicacao)
        grade_equilibrio = QGridLayout()
        grade_equilibrio.setHorizontalSpacing(ESPACO)
        grade_equilibrio.setVerticalSpacing(6)
        self.diferencas_turmas = {}
        for linha, turno in enumerate(("MANHÃ", "TARDE")):
            grade_equilibrio.addWidget(self._rotulo(turno.title()), linha, 0)
            rotulo = self._rotulo("—", "valorQualidade")
            grade_equilibrio.addWidget(rotulo, linha, 1)
            self.diferencas_turmas[turno] = rotulo
        area_equilibrio.addLayout(grade_equilibrio)
        area_equilibrio.addStretch()
        genero = QFrame()
        genero.setObjectName("quadroQualidade")
        area_genero = QVBoxLayout(genero)
        area_genero.setContentsMargins(PADDING_INTERNO, PADDING_INTERNO, PADDING_INTERNO, PADDING_INTERNO)
        area_genero.setSpacing(6)
        area_genero.addWidget(self._rotulo("Maior variação H/M", "subtitulo"))
        self.variacao_genero = self._rotulo("—", "valorQualidade")
        self.variacao_genero.setWordWrap(True)
        area_genero.addWidget(self.variacao_genero)
        self.contexto_variacao = self._rotulo("Turmas com maior variação")
        self.contexto_variacao.hide()
        area_genero.addWidget(self.contexto_variacao)
        self.turmas_variacao_genero = self._rotulo("")
        self.turmas_variacao_genero.setWordWrap(True)
        self.turmas_variacao_genero.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.turmas_variacao_genero.hide()
        area_genero.addWidget(self.turmas_variacao_genero)
        area_genero.addStretch()
        self.grade_qualidade = GradeResponsiva([equilibrio, genero], 240)
        caixa.addWidget(self.grade_qualidade)

        resumo_turnos, caixa = self._painel()
        self._titulo_painel(caixa, "Resumo por turno", "card_resumo_turno")
        self.tabela_resumo_turnos = QWidget()
        self.tabela_resumo_turnos.setAccessibleName("Resumo por turno: linhas Manhã e Tarde")
        grade = QGridLayout(self.tabela_resumo_turnos)
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setHorizontalSpacing(6)
        grade.setVerticalSpacing(0)
        campos = (("turno", "Turno"), ("alunos_alocados", "Alocados"),
                  ("alunos_sem_turma", "Sem turma"), ("capacidade_total", "Capacidade"),
                  ("taxa_ocupacao", "Ocupação"), ("vagas_ociosas", "Vagas livres"))
        self.rotulos_resumo_turnos = {}
        for coluna, (chave, texto) in enumerate(campos):
            cabecalho = self._rotulo(texto, "cabecalhoTabela")
            cabecalho.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cabecalho.setWordWrap(True)
            grade.addWidget(cabecalho, 0, coluna)
            grade.setColumnStretch(coluna, 1)
            self.rotulos_resumo_turnos[chave] = cabecalho
        self.resumo_turnos = {turno: {} for turno in ("MANHÃ", "TARDE")}
        self.cabecalhos_turnos = {}
        for indice, turno in enumerate(self.resumo_turnos):
            separador = QFrame()
            separador.setObjectName("separador")
            separador.setFixedHeight(1)
            grade.addWidget(separador, 1 + indice * 2, 0, 1, len(campos))
            rotulo = self._rotulo(turno.title(), "turnoTabela")
            rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grade.addWidget(rotulo, 2 + indice * 2, 0)
            self.cabecalhos_turnos[turno] = rotulo
            for coluna, (chave, _) in enumerate(campos[1:], 1):
                valor = self._rotulo("—", "valorTabela")
                valor.setAlignment(Qt.AlignmentFlag.AlignCenter)
                grade.addWidget(valor, 2 + indice * 2, coluna)
                self.resumo_turnos[turno][chave] = valor
        caixa.addWidget(self.tabela_resumo_turnos)
        self.grade_resumos = GradeResponsiva([qualidade, resumo_turnos], 390)
        layout.addWidget(self.grade_resumos)
        layout.addStretch()
        self.dashboard.setWidget(conteudo)
        return self.dashboard

    def _atualizar_botoes(self):
        self.importar.setEnabled(not self._ocupado)
        self.gerar.setEnabled(self.arquivo is not None and not self._ocupado)
        self.exportar.setEnabled(self.resultado is not None and not self._ocupado)
        self.exportar_pdf.setEnabled(self.resultado is not None and not self._ocupado)
        self.turma.setEnabled(self.resultado is not None)
        self.busca.setEnabled(self.resultado is not None)
        self.filtro_sexo.setEnabled(self.resultado is not None)
        self.filtro_disponibilidade.setEnabled(self.resultado is not None)
        self.turma_anterior.setEnabled(self.turma.currentIndex() > 0)
        self.turma_proxima.setEnabled(0 <= self.turma.currentIndex() < self.turma.count() - 1)

    def escolher_arquivo(self):
        nome, _ = QFileDialog.getOpenFileName(self, "Importar planilha", "", "Planilha Excel (*.xlsx)")
        if nome:
            self.definir_arquivo(Path(nome))

    def definir_arquivo(self, arquivo):
        if self._ocupado:
            return
        self._limpar_erro()
        self.arquivo = Path(arquivo)
        self.resultado = None
        self.execucao_relatorio = None
        self.nome_arquivo.setText(self.arquivo.name)
        self.nome_arquivo.setToolTip(str(self.arquivo))
        self.turma.clear()
        self.modelo.definir([])
        self.busca.clear()
        self.filtro_sexo.setCurrentIndex(0)
        self.filtro_disponibilidade.setCurrentIndex(0)
        for numero in self.indicadores:
            numero.setText("—")
        for detalhe in self.detalhes_indicadores:
            detalhe.clear()
        for grafico in self.graficos:
            grafico.definir({})
        for rotulo in self.diferencas_turmas.values():
            rotulo.setText("—")
        self.variacao_genero.setText("—")
        self.variacao_genero.setToolTip("")
        self.turmas_variacao_genero.clear()
        self.turmas_variacao_genero.setToolTip("")
        self.turmas_variacao_genero.setAccessibleDescription("")
        self.turmas_variacao_genero.hide()
        self.contexto_variacao.hide()
        for valores in self.resumo_turnos.values():
            for rotulo in valores.values():
                rotulo.setText("—")
        self.dashboard.verticalScrollBar().setValue(0)
        self.relatorio.setPlainText("Nenhuma distribuição realizada para esta planilha.")
        self.avisos.setPlainText("Nenhuma distribuição realizada para esta planilha.")
        self._atualizar_ocorrencias()
        self.contagem.setText("Sem distribuição.")
        self._atualizar_botoes()

    def _iniciar_tarefa(self, funcao, args, ao_concluir=None, *, distribuindo=False, ao_falhar=None):
        if self._ocupado:
            return
        self._limpar_erro()
        self._ocupado = True
        self.carregamento.setVisible(distribuindo)
        self._atualizar_botoes()
        self._tarefa = Tarefa(funcao, *args, parent=self)
        if ao_concluir is not None:
            self._tarefa.concluida.connect(ao_concluir)
        self._tarefa.falhou.connect(ao_falhar or self._falhou)
        self._tarefa.finished.connect(self._finalizar_tarefa)
        self._tarefa.start()

    def gerar_distribuicao(self):
        if self.arquivo is not None and not self._ocupado:
            self.definir_arquivo(self.arquivo)
            self._iniciar_tarefa(self.processador, (self.arquivo,), self.mostrar_resultado, distribuindo=True)

    def mostrar_resultado(self, resultado: ResultadoInterface):
        self._limpar_erro()
        self.carregamento.hide()
        self.resultado = resultado
        self.execucao_relatorio = IdentificacaoExecucao()
        self._mostrar_dashboard(resultado.metricas)
        self.turma.blockSignals(True)
        self.turma.clear()
        self.turma.addItems(list(resultado.grupos))
        self.turma.blockSignals(False)
        self.mostrar_turma(self.turma.currentText())
        inconsistencias, avisos = relatorios_interface(resultado)
        self.relatorio.setPlainText(inconsistencias)
        self.avisos.setPlainText(avisos)
        self._atualizar_ocorrencias(*map(len, separar_ocorrencias(resultado)))
        self._atualizar_botoes()

    def _atualizar_ocorrencias(self, inconsistencias=0, avisos=0):
        for contador, quantidade, titulo in zip(
                self.contadores_ocorrencias, (inconsistencias, avisos), ("inconsistências", "avisos")):
            contador.definir(quantidade)
            contador.setAccessibleName(f"{quantidade} {titulo}")
        for editor, quantidade in zip((self.relatorio, self.avisos), (inconsistencias, avisos)):
            editor.setProperty("vazio", quantidade == 0)
            editor.style().unpolish(editor)
            editor.style().polish(editor)
        self.navegacao.atualizar_ocorrencias(inconsistencias, avisos)

    def _mostrar_dashboard(self, metricas):
        resumo = metricas["resumo"]
        for rotulo, valor in zip(self.indicadores, (
            f"{resumo['alunos_alocados']} / {resumo['total_alunos']}", resumo["alunos_sem_turma"],
            formatar_percentual(resumo["taxa_ocupacao"]), formatar_percentual(resumo["taxa_ociosidade"]),
        )):
            rotulo.setText(str(valor))
        self.detalhes_indicadores[0].setText(
            f"{formatar_percentual(resumo['percentual_alocados'])} dos alunos"
        )
        self.detalhes_indicadores[3].setText(f"{resumo['vagas_ociosas']} vagas livres")
        turmas = metricas["turmas"]
        self.graficos[0].definir({t["nome"]: t["total_alunos"] for t in turmas},
                                 {t["nome"]: t["capacidade"] for t in turmas})
        self.graficos[1].definir({t["nome"]: (t["homens"], t["mulheres"]) for t in turmas})
        for turno, rotulo in self.diferencas_turmas.items():
            amplitude = metricas["balanceamento"][turno]["alunos"]["amplitude"]
            rotulo.setText(texto_diferenca_turmas(amplitude))
        variacao = metricas["destaques"]["variacao_genero"]
        self.variacao_genero.setText(texto_variacao_genero(variacao))
        self.variacao_genero.setToolTip(", ".join(variacao["turmas"]))
        nomes = [nome_turma_visual(nome) for nome in variacao["turmas"]] if variacao["quantidade"] else []
        resumo_turmas = ", ".join(nomes[:LIMITE_TURMAS_VARIACAO])
        if len(nomes) > LIMITE_TURMAS_VARIACAO:
            resumo_turmas += ", ..."
        self.turmas_variacao_genero.setText(resumo_turmas)
        self.turmas_variacao_genero.setToolTip("\n".join(nomes))
        self.turmas_variacao_genero.setAccessibleDescription(", ".join(nomes))
        self.turmas_variacao_genero.setVisible(bool(variacao["quantidade"]))
        self.contexto_variacao.setVisible(bool(variacao["quantidade"]))
        for turno, rotulos in self.resumo_turnos.items():
            dados = metricas["por_turno"][turno]
            for chave, rotulo in rotulos.items():
                if chave == "alunos_alocados":
                    texto = f"{dados[chave]} / {dados['alunos_disponiveis']}"
                elif chave == "taxa_ocupacao":
                    texto = formatar_percentual(dados[chave])
                else:
                    texto = str(dados[chave])
                rotulo.setText(texto)
        self._ajuste_dashboard.start(0)

    def mostrar_turma(self, nome):
        self.busca.clear()
        self.modelo.definir(self.resultado.grupos.get(nome, []) if self.resultado else [])
        self.tabela.scrollToTop()
        self.atualizar_contagem()
        for grafico in self.graficos:
            grafico.selecionar(nome)
        self._atualizar_botoes()

    def atualizar_contagem(self, *_):
        if hasattr(self, "contagem"):
            self.contagem.setText(f"{self.filtro.rowCount()} de {self.modelo.rowCount()} alunos nesta turma")

    def atualizar_filtros(self, *_):
        self.filtro.filtrar(self.filtro_sexo.currentData(), self.filtro_disponibilidade.currentData())
        self.atualizar_contagem()

    def mudar_turma(self, passo):
        indice = self.turma.currentIndex() + passo
        if 0 <= indice < self.turma.count():
            self.turma.setCurrentIndex(indice)

    def mudar_secao(self, indice):
        self.navegacao.selecionar(indice)

    def ir_para_turma(self, nome):
        if self.resultado is not None and nome in self.resultado.grupos:
            self.turma.setCurrentText(nome)
            self.busca.clear()
            self.mudar_secao(1)

    def escolher_destino(self):
        if self.resultado is None or self._ocupado:
            return
        sugerido = self.resultado.origem.with_name(f"{self.resultado.origem.stem}_ensalamento.xlsx")
        nome, _ = QFileDialog.getSaveFileName(self, "Exportar planilha com ensalamento", str(sugerido), "Planilha Excel (*.xlsx)")
        if nome:
            destino = Path(nome)
            if destino.suffix.lower() != ".xlsx":
                destino = Path(str(destino) + ".xlsx")
            self.exportar_para(destino)

    def exportar_para(self, destino):
        if self.resultado is not None:
            self._iniciar_tarefa(self.exportador, (self.resultado, Path(destino)))

    def escolher_destino_pdf(self):
        if self.resultado is None or self._ocupado:
            return
        sugerido = self.resultado.origem.with_name(f"{self.resultado.origem.stem}_relatorio.pdf")
        nome, _ = QFileDialog.getSaveFileName(self, "Exportar relatório PDF", str(sugerido), "Relatório PDF (*.pdf)")
        if nome:
            destino = Path(nome)
            if destino.suffix.lower() != ".pdf":
                destino = Path(str(destino) + ".pdf")
            self.exportar_para_pdf(destino)

    def exportar_para_pdf(self, destino):
        if self.resultado is not None and not self._ocupado:
            self._iniciar_tarefa(
                self.exportador_pdf, (self.resultado, Path(destino), self.execucao_relatorio),
                ao_falhar=self._falhou_pdf,
            )

    def _falhou_pdf(self, mensagem):
        self._falhou(mensagem)
        self.titulo_erro.setText("Não foi possível exportar o relatório PDF.")
        self.orientacao_erro.setText("Verifique se a pasta de destino está disponível para gravação.")

    def _falhou(self, mensagem):
        self.carregamento.hide()
        detalhe = mensagem or ""
        self.detalhe_erro.setText(detalhe)
        self.detalhe_erro.setVisible(bool(detalhe.strip()))
        self.banner_erro.show()

    def _limpar_erro(self):
        self.banner_erro.hide()
        self.titulo_erro.setText("Não foi possível processar a planilha.")
        self.orientacao_erro.setText("Verifique se o arquivo está no formato esperado pelo sistema.")
        self.detalhe_erro.clear()
        self.detalhe_erro.hide()

    def _finalizar_tarefa(self):
        self._ocupado = False
        self.carregamento.hide()
        self._tarefa.deleteLater()
        self._tarefa = None
        self._atualizar_botoes()

    def closeEvent(self, evento):
        if self._ocupado:
            evento.ignore()
        else:
            super().closeEvent(evento)


def iniciar():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ABC Aprendiz")
    app.setOrganizationName("ABC Aprendiz")
    app.setStyle("Fusion")
    paleta = QPalette()
    for papel, cor in ((QPalette.ColorRole.Window, FUNDO),
                       (QPalette.ColorRole.WindowText, TEXTO),
                       (QPalette.ColorRole.Base, BRANCO),
                       (QPalette.ColorRole.AlternateBase, FUNDO),
                       (QPalette.ColorRole.Text, TEXTO),
                       (QPalette.ColorRole.Button, FUNDO_AZUL),
                       (QPalette.ColorRole.ButtonText, TEXTO),
                       (QPalette.ColorRole.Highlight, FUNDO_AZUL),
                       (QPalette.ColorRole.HighlightedText, TEXTO),
                       (QPalette.ColorRole.Light, BRANCO),
                       (QPalette.ColorRole.Mid, BORDA),
                       (QPalette.ColorRole.Dark, TEXTO_SECUNDARIO),
                       (QPalette.ColorRole.ToolTipBase, BRANCO),
                       (QPalette.ColorRole.ToolTipText, TEXTO)):
        paleta.setColor(papel, QColor(cor))
    app.setPalette(paleta)
    app.setFont(fonte_interface())
    janela = JanelaPrincipal()
    tela = app.primaryScreen().availableGeometry()
    janela.resize(min(janela.width(), tela.width()), min(janela.height(), tela.height()))
    janela.show()
    return app.exec()

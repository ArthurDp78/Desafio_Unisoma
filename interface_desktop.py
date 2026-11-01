"""Interface Qt desktop: widgets persistentes, model/view e tarefas em background."""
from __future__ import annotations

from math import ceil
from pathlib import Path
import sys

from PySide6.QtCore import QAbstractTableModel, QEasingCurve, QModelIndex, QPropertyAnimation, QPoint, QRect, QRectF, QSize, QSortFilterProxyModel, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLayout,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QTableView, QVBoxLayout, QWidget,
)

from apresentacao import (
    ResultadoInterface, exportar_planilha, formatar_percentual, processar_planilha,
    texto_busca, texto_diferenca_turmas, texto_variacao_genero,
)

from recursos import caminho_recurso
from tema import (
    AZUL, TURQUESA, VERDE, TURQUESA_ESCURO, TEXTO, TEXTO_SECUNDARIO,
    FUNDO, BRANCO, BORDA, FUNDO_AZUL, ESTILO, ESPACO, MARGEM_PAINEL,
    ICONE, ICONE_CARD, FONTE_GRAFICO, FONTE_EIXO, ALTURA_EIXO,
    ALTURA_GRAFICO_MINIMA, ALTURA_GRAFICO_MAXIMA,
)

LARGURA_DASHBOARD_DESKTOP = 1200
LARGURA_CARDS_TRES_COLUNAS = 820


def icone_svg(nome):
    return QIcon(str(caminho_recurso("assets", "icons", nome + ".svg")))


def icone_widget(nome, tamanho=ICONE):
    widget = QSvgWidget(str(caminho_recurso("assets", "icons", nome + ".svg")))
    widget.setFixedSize(tamanho, tamanho)
    widget.setAccessibleName(nome.replace("_", " "))
    return widget


def fonte_grafico(tamanho=FONTE_GRAFICO):
    fonte = QFont("Segoe UI")
    fonte.setPixelSize(tamanho)
    fonte.setWeight(QFont.Weight.DemiBold)
    return fonte


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
        for indice, (titulo, icone) in enumerate((
            ("Dashboard", "tab_dashboard"), ("Alunos por turma", "tab_alunos"),
            ("Inconsistências", "tab_inconsistencias"), ("Avisos", "tab_avisos"),
        )):
            botao = QPushButton(titulo)
            botao.setIcon(icone_svg(icone))
            botao.setIconSize(QSize(ICONE, ICONE))
            botao.setObjectName("navegacaoBotao")
            botao.setCheckable(True)
            botao.setAccessibleName(titulo)
            botao.setShortcut(f"Alt+{indice + 1}")
            botao.setToolTip(f"{titulo} (Alt+{indice + 1})")
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

    def selecionar(self, indice):
        if not 0 <= indice < len(self.botoes) or indice == self.indice:
            return
        self.indice = indice
        self.botoes[indice].setChecked(True)
        self._posicionar(animar=True)
        self.secao_alterada.emit(indice)

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

    def pesquisar(self, texto):
        self.consulta = texto_busca(texto.strip())
        self.invalidate()

    def filterAcceptsRow(self, linha, parent):
        return self.consulta in texto_busca(self.sourceModel().registros[linha]["Nome"])


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
        self.grade.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
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
        self.dados, self.capacidades = {}, {}
        self.selecionada = ""
        self.areas = []
        self.setAccessibleName("Homens e mulheres por turma" if por_sexo else "Número de alunos por turma")
        self.setMinimumHeight(160)

    def definir(self, dados, capacidades=None):
        self.dados = dados
        self.capacidades = capacidades or {}
        self.setMinimumHeight(max(160, len(dados) * (56 if self.por_sexo else 44) + 8))
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
        altura_linha = max(56 if self.por_sexo else 44, min(80, self.height() / len(self.dados)))
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
        origem = self.area.viewport().mapTo(self, QPoint(0, 0)).x()
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
        painter.setFont(fonte_grafico(FONTE_EIXO))
        painter.setPen(QColor(TEXTO))
        painter.drawText(QRectF(esquerda, 36, direita - esquerda, 25), Qt.AlignmentFlag.AlignCenter, self.titulo)


class JanelaPrincipal(QMainWindow):
    def __init__(self, processador=processar_planilha, exportador=exportar_planilha):
        super().__init__()
        self.processador = processador
        self.exportador = exportador
        self.arquivo = None
        self.resultado = None
        self._tarefa = None
        self._ocupado = False
        self.modo_dashboard = None
        self.indice_dashboard = 0
        self.setWindowTitle("ABC Aprendiz — Ensalamento")
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
        novo_modo = "desktop" if self.width() >= LARGURA_DASHBOARD_DESKTOP else "compacto"
        if novo_modo != self.modo_dashboard:
            self.modo_dashboard = novo_modo
            self.reorganizar_dashboard()
        colunas = 6 if novo_modo == "desktop" else (
            3 if self.width() >= LARGURA_CARDS_TRES_COLUNAS else 2
        )
        if colunas != self.grade_indicadores.colunas:
            self.grade_indicadores.definir_colunas(colunas)

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
        layout.setContentsMargins(17, 14, 17, 14)
        layout.setSpacing(10)
        return frame, layout

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
        cabecalho.addWidget(self._rotulo("ABC Aprendiz", "titulo"))
        cabecalho.addStretch()
        cabecalho.addWidget(self._rotulo("Ensalamento"))
        principal.addLayout(cabecalho)
        arquivo, linha_arquivo = self._painel()
        acoes = QHBoxLayout()
        self.importar = QPushButton("Importar XLSX…")
        self.importar.clicked.connect(self.escolher_arquivo)
        acoes.addWidget(self.importar)
        self.nome_arquivo = self._rotulo("Nenhuma planilha selecionada")
        self.nome_arquivo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        acoes.addWidget(self.nome_arquivo, 1)
        self.gerar = QPushButton("Gerar distribuição")
        self.gerar.setObjectName("primario")
        self.gerar.setEnabled(False)
        self.gerar.clicked.connect(self.gerar_distribuicao)
        acoes.addWidget(self.gerar)
        self.exportar = QPushButton("Exportar XLSX…")
        self.exportar.setObjectName("exportar")
        self.exportar.setEnabled(False)
        self.exportar.clicked.connect(self.escolher_destino)
        acoes.addWidget(self.exportar)
        linha_arquivo.addLayout(acoes)
        principal.addWidget(arquivo)
        self.navegacao = NavegacaoSecoes()
        principal.addWidget(self.navegacao)
        self.secoes = QStackedWidget()
        self.secoes.setAccessibleName("Seção principal")
        self.navegacao.secao_alterada.connect(self.secoes.setCurrentIndex)
        self.secoes.addWidget(self._montar_dashboard())
        alunos, layout_alunos = self._painel()
        alunos.setMinimumSize(360, 200)
        linha_turma = QHBoxLayout()
        linha_turma.addWidget(self._rotulo("Alunos por turma", "secao"))
        linha_turma.addStretch()
        self.turma_anterior = QPushButton("‹")
        self.turma_anterior.setAccessibleName("Turma anterior")
        self.turma_anterior.clicked.connect(lambda: self.mudar_turma(-1))
        self.turma_proxima = QPushButton("›")
        self.turma_proxima.setAccessibleName("Próxima turma")
        self.turma_proxima.clicked.connect(lambda: self.mudar_turma(1))
        linha_turma.addWidget(self.turma_anterior)
        linha_turma.addWidget(self.turma_proxima)
        layout_alunos.addLayout(linha_turma)
        filtros = QHBoxLayout()
        self.turma = QComboBox()
        self.turma.setAccessibleName("Turma exibida")
        self.turma.setMinimumWidth(160)
        self.turma.currentTextChanged.connect(self.mostrar_turma)
        filtros.addWidget(self.turma)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar nome nesta turma")
        self.busca.setAccessibleName("Buscar aluno nesta turma")
        self.busca.setClearButtonEnabled(True)
        filtros.addWidget(self.busca, 1)
        layout_alunos.addLayout(filtros)
        self.modelo = ModeloAlunos(self)
        self.filtro = FiltroAlunos(self)
        self.filtro.setSourceModel(self.modelo)
        self.busca.textChanged.connect(self.filtro.pesquisar)
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
        relatorio, layout_relatorio = self._painel()
        relatorio.setMinimumSize(340, 200)
        layout_relatorio.addWidget(self._rotulo("Inconsistências da instância", "secao"))
        self.relatorio = QPlainTextEdit()
        self.relatorio.setReadOnly(True)
        self.relatorio.setAccessibleName("Relatório agrupado de inconsistências")
        self.relatorio.setPlainText("Nenhuma instância avaliada.")
        layout_relatorio.addWidget(self.relatorio, 1)
        self.secoes.addWidget(relatorio)
        principal.addWidget(self.secoes, 1)
        self.status = self._rotulo("Selecione uma planilha XLSX.")
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        principal.addWidget(self.status)
        self.progresso = QProgressBar()
        self.progresso.setRange(0, 0)
        self.progresso.setTextVisible(False)
        self.progresso.setFixedHeight(4)
        self.progresso.hide()
        principal.addWidget(self.progresso)
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
        layout.setSpacing(13)
        layout.addWidget(self._rotulo("Resumo", "secao"))
        cards = []
        self.indicadores, self.detalhes_indicadores = [], []
        for titulo, fundo, cor in (
            ("Alunos distribuídos", "#E1F3EB", "#207655"),
            ("Alunos sem turma", "#FCF0C7", "#86691E"),
            ("Turmas", "#E3EDFC", "#315F9E"),
            ("Ocupação", "#E1F3EB", "#207655"),
            ("Ociosidade", "#E3EDFC", "#315F9E"),
            ("Inconsistências / avisos", "#FCF0C7", "#86691E"),
        ):
            frame = QFrame()
            frame.setStyleSheet(f"QFrame {{background:{fundo};border:1px solid {fundo};border-radius:12px;}} QLabel {{color:{cor};border:none;}}")
            caixa = QVBoxLayout(frame)
            caixa.setContentsMargins(14, 11, 14, 11)
            caixa.setSpacing(4)
            legenda = QLabel(titulo)
            legenda.setWordWrap(True)
            caixa.addWidget(legenda)
            numero = QLabel("—")
            numero.setStyleSheet("font-size:25px;font-weight:600;")
            caixa.addWidget(numero)
            detalhe = self._rotulo("")
            detalhe.setWordWrap(True)
            caixa.addWidget(detalhe)
            self.indicadores.append(numero)
            self.detalhes_indicadores.append(detalhe)
            cards.append(frame)
        self.grade_indicadores = GradeResponsiva(cards, 170, (6, 3, 2, 1))
        layout.addWidget(self.grade_indicadores)

        self.graficos = [Grafico(), Grafico(por_sexo=True)]
        self.areas_graficos = []
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
        for grafico, titulo, legenda in zip(self.graficos,
                ("Alunos por turma", "Homens e mulheres por turma"),
                ("Alunos / capacidade · Azul: manhã · Verde: tarde", "Azul: homens · Verde: mulheres")):
            painel, caixa = self._painel()
            painel.setFixedHeight(330)
            rotulo = self._rotulo(titulo, "secao")
            rotulo.setWordWrap(True)
            caixa.addWidget(rotulo)
            rotulo = self._rotulo(legenda)
            rotulo.setWordWrap(True)
            caixa.addWidget(rotulo)
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setWidget(grafico)
            self.areas_graficos.append(area)
            caixa.addWidget(area, 1)
            grafico.turma_clicada.connect(self.ir_para_turma)
            paineis.append(painel)
        self.grade_graficos = GradeResponsiva(paineis, 480)
        layout.addWidget(self.grade_graficos)

        qualidade, caixa = self._painel()
        caixa.addWidget(self._rotulo("Qualidade da distribuição", "secao"))
        caixa.addStretch(1)
        equilibrio = QWidget()
        area_equilibrio = QVBoxLayout(equilibrio)
        area_equilibrio.setContentsMargins(0, 0, 0, 0)
        area_equilibrio.setSpacing(12)
        titulo = QLabel("Equilíbrio entre turmas")
        titulo.setStyleSheet("font-weight:600;")
        titulo.setWordWrap(True)
        titulo.setToolTip("Maior diferença de tamanho entre turmas do mesmo turno.")
        area_equilibrio.addWidget(titulo)
        tabela_equilibrio = QWidget()
        tabela_equilibrio.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        grade_equilibrio = QGridLayout(tabela_equilibrio)
        grade_equilibrio.setContentsMargins(0, 0, 0, 0)
        grade_equilibrio.setHorizontalSpacing(20)
        grade_equilibrio.setVerticalSpacing(12)
        self.diferencas_turmas = {}
        for linha, turno in enumerate(("MANHÃ", "TARDE")):
            grade_equilibrio.addWidget(self._rotulo(turno.title()), linha, 0)
            rotulo = QLabel("—")
            rotulo.setStyleSheet("font-size:15px;font-weight:600;")
            grade_equilibrio.addWidget(rotulo, linha, 1)
            self.diferencas_turmas[turno] = rotulo
        area_equilibrio.addWidget(tabela_equilibrio, 0, Qt.AlignmentFlag.AlignLeft)
        area_equilibrio.addStretch()

        genero = QWidget()
        area_genero = QVBoxLayout(genero)
        area_genero.setContentsMargins(0, 0, 0, 0)
        area_genero.setSpacing(12)
        titulo = QLabel("Maior variação H/M")
        titulo.setStyleSheet("font-weight:600;")
        area_genero.addWidget(titulo)
        self.variacao_genero = QLabel("—")
        self.variacao_genero.setStyleSheet("font-size:15px;font-weight:600;")
        self.variacao_genero.setWordWrap(True)
        area_genero.addWidget(self.variacao_genero)
        self.turmas_variacao_genero = self._rotulo("")
        self.turmas_variacao_genero.setWordWrap(True)
        self.turmas_variacao_genero.hide()
        area_genero.addWidget(self.turmas_variacao_genero)
        area_genero.addStretch()
        self.grade_qualidade = GradeResponsiva([equilibrio, genero], 290)
        self.grade_qualidade.setMaximumWidth(640)
        self.grade_qualidade.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        centralizar_qualidade = QHBoxLayout()
        centralizar_qualidade.addStretch(1)
        centralizar_qualidade.addWidget(self.grade_qualidade, 10)
        centralizar_qualidade.addStretch(1)
        caixa.addLayout(centralizar_qualidade)
        caixa.addStretch(1)

        resumo_turnos, caixa = self._painel()
        caixa.addWidget(self._rotulo("Resumo por turno", "secao"))
        caixa.addStretch(1)
        self.tabela_resumo_turnos = QWidget()
        self.tabela_resumo_turnos.setAccessibleName("Resumo por turno: Manhã e Tarde")
        self.tabela_resumo_turnos.setMaximumWidth(520)
        grade = QGridLayout(self.tabela_resumo_turnos)
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setHorizontalSpacing(18)
        grade.setVerticalSpacing(11)
        grade.setColumnStretch(0, 1)
        self.resumo_turnos = {turno: {} for turno in ("MANHÃ", "TARDE")}
        self.cabecalhos_turnos = {}
        self.rotulos_resumo_turnos = {}
        for coluna, turno in enumerate(self.resumo_turnos, 1):
            cabecalho = QLabel(turno)
            cabecalho.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cabecalho.setStyleSheet("font-size:12px;font-weight:600;")
            grade.addWidget(cabecalho, 0, coluna)
            self.cabecalhos_turnos[turno] = cabecalho
            grade.setColumnStretch(coluna, 1)
        for linha, (chave, texto) in enumerate((
            ("alunos_alocados", "Alocados"),
            ("alunos_sem_turma", "Sem turma"), ("capacidade_total", "Capacidade"),
            ("taxa_ocupacao", "Ocupação"), ("vagas_ociosas", "Vagas livres"),
        ), 1):
            rotulo_linha = self._rotulo(texto)
            rotulo_linha.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            grade.addWidget(rotulo_linha, linha, 0)
            self.rotulos_resumo_turnos[chave] = rotulo_linha
            for coluna, turno in enumerate(self.resumo_turnos, 1):
                rotulo = QLabel("—")
                rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
                rotulo.setStyleSheet("font-size:14px;font-weight:600;")
                grade.addWidget(rotulo, linha, coluna)
                self.resumo_turnos[turno][chave] = rotulo
        centralizar = QHBoxLayout()
        centralizar.addStretch(1)
        centralizar.addWidget(self.tabela_resumo_turnos, 3)
        centralizar.addStretch(1)
        caixa.addLayout(centralizar)
        caixa.addStretch(1)
        self.grade_resumos = GradeResponsiva([qualidade, resumo_turnos], 390)
        layout.addWidget(self.grade_resumos)
        layout.addStretch()
        self.dashboard.setWidget(conteudo)
        return self.dashboard

    def _atualizar_botoes(self):
        self.importar.setEnabled(not self._ocupado)
        self.gerar.setEnabled(self.arquivo is not None and not self._ocupado)
        self.exportar.setEnabled(self.resultado is not None and not self._ocupado)
        self.turma.setEnabled(self.resultado is not None)
        self.busca.setEnabled(self.resultado is not None)
        self.turma_anterior.setEnabled(self.turma.currentIndex() > 0)
        self.turma_proxima.setEnabled(0 <= self.turma.currentIndex() < self.turma.count() - 1)

    def escolher_arquivo(self):
        nome, _ = QFileDialog.getOpenFileName(self, "Importar planilha", "", "Planilha Excel (*.xlsx)")
        if nome:
            self.definir_arquivo(Path(nome))

    def definir_arquivo(self, arquivo):
        if self._ocupado:
            return
        self.arquivo = Path(arquivo)
        self.resultado = None
        self.nome_arquivo.setText(self.arquivo.name)
        self.nome_arquivo.setToolTip(str(self.arquivo))
        self.turma.clear()
        self.modelo.definir([])
        self.busca.clear()
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
        self.turmas_variacao_genero.hide()
        for valores in self.resumo_turnos.values():
            for rotulo in valores.values():
                rotulo.setText("—")
        self.dashboard.verticalScrollBar().setValue(0)
        self.relatorio.setPlainText("Nenhuma distribuição realizada para esta planilha.")
        self.contagem.setText("Sem distribuição.")
        self.status.setText("Planilha selecionada.")
        self._atualizar_botoes()

    def _iniciar_tarefa(self, funcao, args, ao_concluir, mensagem):
        if self._ocupado:
            return
        self._ocupado = True
        self.status.setText(mensagem)
        self.progresso.show()
        self._atualizar_botoes()
        self._tarefa = Tarefa(funcao, *args, parent=self)
        self._tarefa.concluida.connect(ao_concluir)
        self._tarefa.falhou.connect(self._falhou)
        self._tarefa.finished.connect(self._finalizar_tarefa)
        self._tarefa.start()

    def gerar_distribuicao(self):
        if self.arquivo is not None and not self._ocupado:
            self.definir_arquivo(self.arquivo)
            self._iniciar_tarefa(self.processador, (self.arquivo,), self.mostrar_resultado, "Calculando a distribuição…")

    def mostrar_resultado(self, resultado: ResultadoInterface):
        self.resultado = resultado
        self._mostrar_dashboard(resultado.metricas, len(resultado.inconsistencias))
        self.turma.blockSignals(True)
        self.turma.clear()
        self.turma.addItems(list(resultado.grupos))
        self.turma.blockSignals(False)
        self.mostrar_turma(self.turma.currentText())
        self.relatorio.setPlainText(resultado.relatorio())
        self.status.setText("Distribuição concluída. A planilha original ainda não foi alterada.")
        self._atualizar_botoes()

    def _mostrar_dashboard(self, metricas, avisos):
        resumo = metricas["resumo"]
        for rotulo, valor in zip(self.indicadores, (
            resumo["alunos_alocados"], resumo["alunos_sem_turma"], resumo["total_turmas"],
            formatar_percentual(resumo["taxa_ocupacao"]), formatar_percentual(resumo["taxa_ociosidade"]), avisos,
        )):
            rotulo.setText(str(valor))
        self.detalhes_indicadores[0].setText(
            f"de {resumo['total_alunos']} alunos · {formatar_percentual(resumo['percentual_alocados'])}"
        )
        self.detalhes_indicadores[4].setText(f"{resumo['vagas_ociosas']} vagas livres")
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
        self.turmas_variacao_genero.setText(", ".join(variacao["turmas"]) if variacao["quantidade"] else "")
        self.turmas_variacao_genero.setVisible(bool(variacao["quantidade"]))
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
            self._iniciar_tarefa(self.exportador, (self.resultado, Path(destino)), self._exportado, "Exportando a planilha…")

    def _exportado(self, destino):
        self.status.setText(f"Planilha exportada: {destino}")
        self.status.setToolTip(str(destino))

    def _falhou(self, mensagem):
        self.status.setText("Não foi possível concluir a operação.")
        QMessageBox.critical(self, "Operação não concluída", mensagem)

    def _finalizar_tarefa(self):
        self._ocupado = False
        self.progresso.hide()
        self._tarefa.deleteLater()
        self._tarefa = None
        self._atualizar_botoes()

    def closeEvent(self, evento):
        if self._ocupado:
            self.status.setText("Aguarde a conclusão da operação antes de fechar.")
            evento.ignore()
        else:
            super().closeEvent(evento)


def iniciar():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ABC Aprendiz")
    app.setOrganizationName("ABC Aprendiz")
    app.setStyle("Fusion")
    paleta = QPalette()
    for papel, cor in ((QPalette.ColorRole.Window, "#F2F5FA"),
                       (QPalette.ColorRole.WindowText, TEXTO),
                       (QPalette.ColorRole.Base, "#FFFFFF"),
                       (QPalette.ColorRole.AlternateBase, "#F3F7FD"),
                       (QPalette.ColorRole.Text, TEXTO),
                       (QPalette.ColorRole.Button, "#E8EFFB"),
                       (QPalette.ColorRole.ButtonText, TEXTO),
                       (QPalette.ColorRole.Highlight, "#DFE9F5"),
                       (QPalette.ColorRole.HighlightedText, TEXTO),
                       (QPalette.ColorRole.Light, "#FFFFFF"),
                       (QPalette.ColorRole.Mid, "#CED8E5"),
                       (QPalette.ColorRole.Dark, "#A5B4C7"),
                       (QPalette.ColorRole.ToolTipBase, "#FFFFFF"),
                       (QPalette.ColorRole.ToolTipText, TEXTO)):
        paleta.setColor(papel, QColor(cor))
    app.setPalette(paleta)
    app.setFont(QFont("Segoe UI", 10))
    janela = JanelaPrincipal()
    tela = app.primaryScreen().availableGeometry()
    janela.resize(min(janela.width(), tela.width()), min(janela.height(), tela.height()))
    janela.show()
    return app.exec()

"""Identidade visual ABC Aprendiz: cores, dimensões e QSS compartilhados."""
from string import Template
from PySide6.QtGui import QFont

AZUL = "#2A469A"
TURQUESA = "#3DBD9D"
VERDE = "#9CCD58"
TURQUESA_ESCURO = "#2E9587"
TEXTO = "#24365E"
TEXTO_SECUNDARIO = "#475A78"
FUNDO = "#F5F7FC"
BRANCO = "#FFFFFF"
BORDA = "#D9E2F1"
FUNDO_AZUL = "#EDF1FA"
FUNDO_VERDE = "#EDF7E5"
FUNDO_TURQUESA = "#EAF8F3"
ALERTA = "#B86B12"
FUNDO_ALERTA = "#FFF1DC"
RAIO = 12
ESPACO = 12
ESPACO_SECOES = 16
MARGEM_PAINEL = 16
ICONE = 20
ICONE_CARD = 24
CONTADOR_MINIMO = 24
PADDING_ABA_VERTICAL = 10
PADDING_ABA_HORIZONTAL = 14
FAMILIAS_FONTES = ("Segoe UI", "Noto Sans", "Arial", "Liberation Sans", "DejaVu Sans")
FAMILIAS_QSS = ", ".join(f"'{nome}'" for nome in FAMILIAS_FONTES) + ", sans-serif"
FONTE_BASE = 14
FONTE_GRAFICO = 14
FONTE_EIXO = 14
FONTE_TITULO = 17
ALTURA_GRAFICO_MINIMA = 400
ALTURA_GRAFICO_MAXIMA = 560
ALTURA_EIXO = 66


def fonte_interface(tamanho=FONTE_BASE, peso=QFont.Weight.Normal):
    fonte = QFont()
    fonte.setFamilies(list(FAMILIAS_FONTES))
    fonte.setPixelSize(tamanho)
    fonte.setWeight(peso)
    return fonte


ESTILO = Template("""
QMainWindow, QWidget#central { background: $FUNDO; color: $TEXTO; }
QWidget { font-family: $FAMILIAS_QSS; font-size: ${FONTE_BASE}px; font-weight: 400; color: $TEXTO; }
QFrame#painel, QFrame#cardResumo { background: $BRANCO; border: 1px solid $BORDA; border-radius: ${RAIO}px; }
QFrame#iconeCard { background: $FUNDO_AZUL; border: none; border-radius: 11px; }
QFrame#iconeCard[tipo="positivo"] { background: $FUNDO_VERDE; }
QFrame#iconeCard[tipo="turquesa"] { background: $FUNDO_TURQUESA; }
QLabel { background: transparent; border: none; }
QLabel#titulo { font-size: 22px; font-weight: 600; color: $AZUL; }
QLabel#secao { font-size: ${FONTE_TITULO}px; font-weight: 600; color: $AZUL; }
QLabel#subtitulo { font-size: 14px; font-weight: 600; color: $TEXTO; }
QLabel#eixo { font-size: ${FONTE_EIXO}px; font-weight: 600; color: $TEXTO; }
QLabel#discreto { color: $TEXTO_SECUNDARIO; font-size: 13px; }
QLabel#legenda { color: $TEXTO; font-size: 14px; }
QLabel#numeroCard { font-size: 24px; font-weight: 600; color: $AZUL; }
QLabel#valorQualidade { font-size: 16px; font-weight: 600; color: $AZUL; }
QLabel#valorTabela { font-size: 14px; font-weight: 400; color: $TEXTO; padding: 5px 2px; }
QLabel#turnoTabela { font-size: 14px; font-weight: 600; color: $AZUL; padding: 5px 2px; }
QLabel#cabecalhoTabela { font-size: 13px; font-weight: 600; color: $AZUL; background: $FUNDO_AZUL; padding: 7px 3px; }
QLabel#badgeOcorrencias { color: $ALERTA; font-size: 12px; font-weight: 600; }
QLabel#badgeOcorrencias[vazio="true"] { color: $TEXTO_SECUNDARIO; }
QFrame#separador { background: $BORDA; border: none; }
QFrame#navegacao { background: white; border: 1px solid $BORDA; border-radius: ${RAIO}px; }
QFrame#marcador { background: $AZUL; border: none; border-radius: 2px; }
QPushButton { background: $FUNDO_AZUL; border: 1px solid $BORDA; border-radius: 9px;
              padding: 8px 14px; min-height: 20px; font-weight: 400; color: $AZUL; }
QPushButton:hover { background: #E2E9F8; border-color: #A7B8DE; }
QPushButton:pressed { background: #D7E1F6; }
QPushButton:disabled { color: #75829B; background: #F0F3F8; border-color: #E1E6EF; }
QPushButton#primario { background: $AZUL; color: white; border-color: $AZUL; }
QPushButton#primario:hover { background: #21397F; }
QPushButton#primario:disabled { background: #DCE3F1; color: #6C7A96; border-color: #DCE3F1; }
QPushButton#exportar { background: white; color: $AZUL; border-color: #A7B8DE; }
QPushButton#exportar:hover { background: $FUNDO_AZUL; }
QPushButton#navegacaoBotao { background: transparent; border: none; border-radius: 8px;
                          color: $TEXTO_SECUNDARIO; padding: 0; }
QLabel#textoNavegacao { color: $TEXTO_SECUNDARIO; font-size: 14px; font-weight: 400; }
QLabel#textoNavegacao[ativa="true"] { color: $AZUL; font-weight: 600; }
QPushButton#navegacaoBotao:hover { background: #F3F6FC; color: $AZUL; }
QPushButton#navegacaoBotao:checked { background: $FUNDO_AZUL; color: $AZUL; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border-color: $AZUL; }
QLineEdit, QComboBox { background: white; border: 1px solid $BORDA; border-radius: 8px;
                     padding: 7px 10px; min-height: 20px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { selection-background-color: $FUNDO_AZUL; selection-color: $TEXTO; }
QTableView { background: white; alternate-background-color: #F3F6FC; border: none;
             selection-background-color: #E1E8F8; selection-color: $TEXTO; gridline-color: $BORDA; }
QHeaderView::section { background: $FUNDO_AZUL; color: $AZUL; border: none; border-bottom: 1px solid $BORDA;
                       padding: 9px; font-weight: 600; }
QPlainTextEdit { background: white; border: none; selection-background-color: $FUNDO_AZUL; }
QPlainTextEdit#textoOcorrencias[vazio="true"] { color: $TEXTO_SECUNDARIO; }
QScrollArea { background: white; border: none; }
QScrollBar:vertical { background: #F0F3FA; width: 12px; margin: 0; border-radius: 6px; }
QScrollBar::handle:vertical { background: #A1B2D3; min-height: 28px; border-radius: 6px; }
QScrollBar::handle:vertical:hover { background: #7F96C4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QProgressBar { background: $FUNDO_TURQUESA; border: none; height: 4px; }
QProgressBar::chunk { background: $TURQUESA_ESCURO; }
""").substitute({k: str(v) for k, v in globals().copy().items() if k.isupper()})

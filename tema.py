"""Identidade visual ABC Aprendiz: cores, dimensões e QSS compartilhados."""
from string import Template
from PySide6.QtGui import QFont
from recursos import caminho_recurso

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
BORDA_ALERTA = "#EBD6B4"
RAIO = 12
RAIO_INTERNO = 10
PADDING_INTERNO = 12
ESPACO = 12
ESPACO_SECOES = 16
LIMITE_TURMAS_VARIACAO = 4
MARGEM_PAINEL = 16
ICONE = 20
ICONE_CARD = 24
CONTADOR_MINIMO = 24
PADDING_ABA_VERTICAL = 10
PADDING_ABA_HORIZONTAL = 14
ALFA_ABA_INATIVA = 24
ALFA_ABA_HOVER = 36
ALFA_ABA_ATIVA = 48
FAMILIAS_FONTES = ("Inter", "Segoe UI", "Noto Sans", "Arial", "Liberation Sans", "DejaVu Sans")
FAMILIAS_QSS = ", ".join(f"'{nome}'" for nome in FAMILIAS_FONTES) + ", sans-serif"
FONTE_BASE = 14
FONTE_GRAFICO = 14
FONTE_EIXO = 14
FONTE_TITULO = 17
ALTURA_GRAFICO_MINIMA = 400
ALTURA_GRAFICO_MAXIMA = 560
AJUSTE_MAXIMO_GRAFICOS = 32
ALTURA_EIXO = 66
CHEVRON_DROPDOWN = caminho_recurso("assets", "icons", "chevron_down.svg").as_posix()


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
QFrame#bannerErro { background: $FUNDO_ALERTA; border: 1px solid $BORDA_ALERTA; border-radius: ${RAIO}px; }
QFrame#quadroQualidade { background: $FUNDO; border: 1px solid $BORDA; border-radius: ${RAIO_INTERNO}px; }
QFrame#iconeCard { background: $FUNDO_AZUL; border: none; border-radius: 11px; }
QFrame#iconeCard[tipo="positivo"] { background: $FUNDO_VERDE; }
QFrame#iconeCard[tipo="turquesa"] { background: $FUNDO_TURQUESA; }
QLabel { background: transparent; border: none; }
QLabel#titulo { font-size: 22px; font-weight: 500; color: $AZUL; }
QLabel#secao { font-size: ${FONTE_TITULO}px; font-weight: 600; color: $AZUL; }
QLabel#subtitulo { font-size: 14px; font-weight: 500; color: $TEXTO; }
QLabel#eixo { font-size: ${FONTE_EIXO}px; font-weight: 500; color: $TEXTO; }
QLabel#discreto { color: $TEXTO_SECUNDARIO; font-size: 13px; }
QLabel#avisoConclusao { color: $TEXTO; font-size: 13px; background: $FUNDO_TURQUESA;
                      border: 1px solid $BORDA; border-radius: ${RAIO_INTERNO}px; padding: 8px 12px; }
QLabel#legenda { color: $TEXTO; font-size: 14px; }
QLabel#numeroCard { font-size: 24px; font-weight: 500; color: $AZUL; }
QLabel#valorQualidade { font-size: 16px; font-weight: 500; color: $AZUL; }
QLabel#valorTabela { font-size: 14px; font-weight: 500; color: $TEXTO; padding: 5px 2px; }
QLabel#turnoTabela { font-size: 14px; font-weight: 500; color: $AZUL; padding: 5px 2px; }
QLabel#cabecalhoTabela { font-size: 13px; font-weight: 500; color: $AZUL; background: $FUNDO_AZUL; padding: 7px 3px; }
QLabel#badgeOcorrencias { color: $ALERTA; font-size: 12px; font-weight: 600; }
QLabel#badgeOcorrencias[vazio="true"] { color: $TEXTO_SECUNDARIO; }
QLabel#badgeOcorrencias[tipo="inconsistencias"] { color: $ALERTA; }
QLabel#badgeOcorrencias[tipo="avisos"] { color: $AZUL; }
QFrame#separador { background: $BORDA; border: none; }
QFrame#navegacao { background: white; border: 1px solid $BORDA; border-radius: ${RAIO}px; }
QFrame#marcador { background: $AZUL; border: none; border-radius: 2px; }
QPushButton { background: $FUNDO_AZUL; border: 1px solid $BORDA; border-radius: 9px;
              padding: 8px 14px; min-height: 20px; font-weight: 500; color: $AZUL; }
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
QLabel#textoNavegacao[ativa="true"] { color: $AZUL; font-weight: 500; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border-color: $AZUL; }
QLineEdit, QComboBox { background: white; border: 1px solid $BORDA; border-radius: 8px;
                     padding: 7px 10px; min-height: 20px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox#seletorTurma, QComboBox#filtroSexo, QComboBox#filtroDisponibilidade {
    padding: 8px 38px 8px 10px;
}
QLineEdit#buscaAlunos { padding: 8px 10px; }
QComboBox#seletorTurma::drop-down, QComboBox#filtroSexo::drop-down, QComboBox#filtroDisponibilidade::drop-down {
    subcontrol-origin: padding; subcontrol-position: top right; width: 30px;
    background: $FUNDO_AZUL; border-left: 1px solid $BORDA;
    border-top-right-radius: 8px; border-bottom-right-radius: 8px;
}
QComboBox#seletorTurma::down-arrow, QComboBox#filtroSexo::down-arrow, QComboBox#filtroDisponibilidade::down-arrow {
    image: url("$CHEVRON_DROPDOWN"); width: 14px; height: 14px;
}
QComboBox QAbstractItemView { selection-background-color: $FUNDO_AZUL; selection-color: $TEXTO; }
QTableView { background: white; alternate-background-color: #F3F6FC; border: none;
             selection-background-color: #E1E8F8; selection-color: $TEXTO; gridline-color: $BORDA; }
QHeaderView::section { background: $FUNDO_AZUL; color: $AZUL; border: none; border-bottom: 1px solid $BORDA;
                       padding: 9px; font-weight: 500; }
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


def _estilo_abas():
    regras = []
    for secao, cor in (("dashboard", AZUL), ("alunos", TURQUESA), ("ocorrencias", VERDE)):
        rgb = ", ".join(str(int(cor[i:i + 2], 16)) for i in (1, 3, 5))
        for estado, alfa in (("", ALFA_ABA_INATIVA), (":hover", ALFA_ABA_HOVER), (":checked", ALFA_ABA_ATIVA)):
            regras.append(
                f'QPushButton#navegacaoBotao[secao="{secao}"]{estado} {{ background: rgba({rgb}, {alfa}); }}')
        regras.append(f'QFrame#marcador[secao="{secao}"] {{ background: {cor}; }}')
    return "\n".join(regras)


ESTILO += "\n" + _estilo_abas()

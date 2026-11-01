"""Relatório PDF nativo do Qt, baseado somente na distribuição já calculada."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import ceil
from pathlib import Path
import os
import tempfile
from uuid import uuid4

from PySide6.QtCore import QFile, QIODevice, QMarginsF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import (
    QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter,
    QPen, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, QTextFormat,
    QTextFrameFormat, QTextImageFormat, QTextLength, QTextOption, QTextTableFormat,
)

from apresentacao import (
    ResultadoInterface, formatar_percentual, nome_turma_visual, separar_ocorrencias,
    texto_diferenca_turmas, texto_variacao_genero,
)
from recursos import caminho_recurso
from tema import (
    ALERTA, AZUL, BORDA, BRANCO, FUNDO, FUNDO_ALERTA, FUNDO_AZUL,
    TEXTO, TEXTO_SECUNDARIO, TURQUESA, TURQUESA_ESCURO, VERDE, fonte_interface,
)


@dataclass(frozen=True)
class IdentificacaoExecucao:
    codigo: str = field(default_factory=lambda: uuid4().hex[:12].upper())
    concluida_em: datetime = field(default_factory=lambda: datetime.now().astimezone())


def _fonte(tamanho=9.5, peso=QFont.Weight.Normal):
    fonte = fonte_interface()
    fonte.setPointSizeF(tamanho)
    fonte.setWeight(peso)
    return fonte


def _caracteres(tamanho=9.5, peso=QFont.Weight.Normal, cor=TEXTO):
    formato = QTextCharFormat()
    formato.setFont(_fonte(tamanho, peso))
    formato.setForeground(QColor(cor))
    return formato


class _Conteudo:
    def __init__(self, largura, altura, dispositivo):
        self.largura = largura
        self.doc = QTextDocument()
        self.doc.documentLayout().setPaintDevice(dispositivo)
        self.doc.setDefaultFont(_fonte())
        self.doc.setDocumentMargin(0)
        self.doc.setPageSize(QSizeF(largura, altura))
        opcao = self.doc.defaultTextOption()
        opcao.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.doc.setDefaultTextOption(opcao)
        self.cursor = QTextCursor(self.doc)
        self._imagens = 0

    def texto(self, texto, tamanho=9.5, peso=QFont.Weight.Normal, cor=TEXTO, depois=6, nova_pagina=False):
        bloco = QTextBlockFormat()
        bloco.setBottomMargin(depois)
        bloco.setNonBreakableLines(True)
        if nova_pagina:
            bloco.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
        self.cursor.setBlockFormat(bloco)
        self.cursor.insertText(str(texto), _caracteres(tamanho, peso, cor))
        self.cursor.insertBlock(QTextBlockFormat(), _caracteres())

    def titulo(self, texto, nova_pagina=False):
        self.texto(texto, 14, QFont.Weight.DemiBold, AZUL, 12, nova_pagina)

    def tabela(self, cabecalhos, linhas, larguras, *, centralizadas=(),
               cor=AZUL, fundo=FUNDO_AZUL, identificacao=None, tamanho=9.5, padding=6):
        formato = QTextTableFormat()
        formato.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        formato.setColumnWidthConstraints([
            QTextLength(QTextLength.Type.PercentageLength, largura * 100) for largura in larguras
        ])
        formato.setBorder(0.4)
        formato.setBorderBrush(QColor(BORDA))
        formato.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        formato.setBorderCollapse(True)
        formato.setCellSpacing(0)
        formato.setCellPadding(padding)
        formato.setBottomMargin(10)
        inicio = 2 if identificacao else 1
        formato.setHeaderRowCount(inicio)
        tabela = self.cursor.insertTable(len(linhas) + inicio, len(cabecalhos), formato)

        def preencher(linha, coluna, valor, *, cabecalho=False, mesclada=False):
            celula = tabela.cellAt(linha, coluna)
            estilo = celula.format()
            estilo.setBackground(QColor(fundo if cabecalho else (BRANCO if (linha - inicio) % 2 == 0 else FUNDO)))
            celula.setFormat(estilo)
            cursor = celula.firstCursorPosition()
            bloco = QTextBlockFormat()
            bloco.setNonBreakableLines(True)
            if coluna in centralizadas and not mesclada:
                bloco.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cursor.setBlockFormat(bloco)
            cursor.insertText(str(valor), _caracteres(
                9 if cabecalho else tamanho,
                QFont.Weight.Medium if cabecalho else QFont.Weight.Normal,
                cor if cabecalho else TEXTO,
            ))

        if identificacao:
            tabela.mergeCells(0, 0, 1, len(cabecalhos))
            preencher(0, 0, identificacao, cabecalho=True, mesclada=True)
        for coluna, nome in enumerate(cabecalhos):
            preencher(inicio - 1, coluna, nome, cabecalho=True)
        for linha, valores in enumerate(linhas, inicio):
            for coluna, valor in enumerate(valores):
                preencher(linha, coluna, valor)
        self.cursor.movePosition(QTextCursor.MoveOperation.End)
        self.cursor.setBlockFormat(QTextBlockFormat())
        self.cursor.setCharFormat(_caracteres())

    def imagem(self, imagem, altura):
        self._imagens += 1
        nome = QUrl(f"relatorio:grafico-{self._imagens}")
        self.doc.addResource(QTextDocument.ResourceType.ImageResource, nome, imagem)
        formato = QTextImageFormat()
        formato.setName(nome.toString())
        formato.setWidth(self.largura)
        formato.setHeight(altura)
        bloco = QTextBlockFormat()
        bloco.setBottomMargin(12)
        bloco.setNonBreakableLines(True)
        self.cursor.setBlockFormat(bloco)
        self.cursor.insertImage(formato)
        self.cursor.insertBlock(QTextBlockFormat(), _caracteres())


def _grafico(turmas, todas_turmas, largura, por_sexo, parte, partes):
    """Renderiza todas as barras em blocos legíveis, sem capturar widgets/scrolls."""
    linha = 32 if por_sexo else 24
    topo, rodape = 76, 48
    altura = topo + len(turmas) * linha + rodape
    escala = 3
    imagem = QImage(ceil(largura * escala), ceil(altura * escala), QImage.Format.Format_ARGB32_Premultiplied)
    imagem.fill(QColor(BRANCO))
    pintor = QPainter(imagem)
    try:
        pintor.scale(escala, escala)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)

        def texto(rect, valor, tamanho=9, cor=TEXTO, peso=QFont.Weight.Normal, alinhamento=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
            fonte = fonte_interface(ceil(tamanho), peso)
            pintor.setFont(fonte)
            pintor.setPen(QColor(cor))
            pintor.drawText(rect, alinhamento, str(valor))

        titulo = "Homens e mulheres por turma" if por_sexo else "Alunos por turma"
        if partes > 1:
            titulo += f" · {parte} / {partes}"
        texto(QRectF(0, 0, largura, 22), titulo, 12, AZUL, QFont.Weight.DemiBold)
        legenda = ("Azul: homens · Turquesa: mulheres" if por_sexo else
                   "Azul: manhã · Turquesa: tarde · Valores: alunos / capacidade")
        texto(QRectF(0, 25, largura, 18), legenda, 8.5)
        texto(QRectF(0, 49, 100, 18), "Turma", 9, TEXTO, QFont.Weight.Medium)
        esquerda, direita = 102, largura - 65
        valores = ([t[chave] for t in todas_turmas for chave in ("homens", "mulheres")]
                   if por_sexo else [t["capacidade"] for t in todas_turmas])
        passo = max(1, ceil(max(valores, default=0) / 4))
        maximo = passo * 4
        base = topo + len(turmas) * linha
        for i in range(5):
            x = esquerda + (direita - esquerda) * i / 4
            pintor.setPen(QPen(QColor(BORDA), 0.5))
            pintor.drawLine(QRectF(x, topo, 0, base - topo).topLeft(), QRectF(x, topo, 0, base - topo).bottomLeft())
            texto(QRectF(x - 15, base + 5, 30, 15), i * passo, 8.5, alinhamento=Qt.AlignmentFlag.AlignCenter)
        for i, turma in enumerate(turmas):
            y = topo + i * linha
            texto(QRectF(0, y, esquerda - 8, linha), nome_turma_visual(turma["nome"]), 8.5)
            if por_sexo:
                barras = ((turma["homens"], AZUL), (turma["mulheres"], TURQUESA))
                for j, (quantidade, cor) in enumerate(barras):
                    largura_barra = quantidade / maximo * (direita - esquerda)
                    pintor.fillRect(QRectF(esquerda, y + 3 + j * 14, largura_barra, 10), QColor(cor))
                    texto(QRectF(esquerda + largura_barra + 5, y + j * 14, 45, 16), quantidade, 8.5)
            else:
                pintor.fillRect(QRectF(esquerda, y + 5, turma["capacidade"] / maximo * (direita - esquerda), 14), QColor(FUNDO_AZUL))
                cor = AZUL if turma["turno"] == "MANHÃ" else TURQUESA_ESCURO
                pintor.fillRect(QRectF(esquerda, y + 5, turma["total_alunos"] / maximo * (direita - esquerda), 14), QColor(cor))
                texto(QRectF(direita + 7, y, 58, linha), f"{turma['total_alunos']} / {turma['capacidade']}", 8.5)
        pintor.setPen(QPen(QColor(AZUL), 0.8))
        pintor.drawLine(QRectF(esquerda, base, direita - esquerda, 0).topLeft(), QRectF(esquerda, base, direita - esquerda, 0).topRight())
        texto(QRectF(esquerda, base + 24, direita - esquerda, 18), "Quantidade de alunos", 9,
              peso=QFont.Weight.Medium, alinhamento=Qt.AlignmentFlag.AlignCenter)
    finally:
        pintor.end()
    return imagem, altura


def _montar_conteudo(conteudo, resultado, execucao, emitido_em):
    metricas = resultado.metricas
    resumo = metricas["resumo"]
    conteudo.texto("Relatório de distribuição", 20, QFont.Weight.Medium, AZUL, 14)
    conteudo.texto(f"Arquivo: {resultado.origem.name}", peso=QFont.Weight.Medium)
    conteudo.texto(f"Execução: {execucao.codigo} · Concluída em {execucao.concluida_em.strftime('%d/%m/%Y às %H:%M:%S %z')}", 8.5, cor=TEXTO_SECUNDARIO)
    conteudo.texto(f"PDF emitido em {emitido_em.strftime('%d/%m/%Y às %H:%M:%S %z')}", 8.5, cor=TEXTO_SECUNDARIO, depois=14)
    conteudo.titulo("Resumo geral")
    conteudo.tabela(
        ["Alunos processados\n(válidos)", "Alocados", "Sem turma", "Ocupação", "Ociosidade"],
        [[resumo["total_alunos"], resumo["alunos_alocados"], resumo["alunos_sem_turma"],
          formatar_percentual(resumo["taxa_ocupacao"]), formatar_percentual(resumo["taxa_ociosidade"])]],
        [0.2] * 5, centralizadas=range(5), tamanho=12,
    )
    conteudo.texto(f"Capacidade: {resumo['capacidade_total']} vagas · Vagas livres: {resumo['vagas_ociosas']} · Turmas: {resumo['total_turmas']}", 9)
    conteudo.texto("O total de alunos processados considera os registros válidos da distribuição. Os registros inválidos são apresentados em Inconsistências.", 8.5, cor=TEXTO_SECUNDARIO, depois=12)
    conteudo.titulo("Resumo por turno")
    linhas = []
    for turno, dados in metricas["por_turno"].items():
        linhas.append([turno.title(), f"{dados['alunos_alocados']} / {dados['alunos_disponiveis']}",
                       dados["alunos_sem_turma"], dados["capacidade_total"],
                       formatar_percentual(dados["taxa_ocupacao"]),
                       formatar_percentual(dados["taxa_ociosidade"]), dados["vagas_ociosas"]])
    conteudo.tabela(["Turno", "Alocados", "Sem turma", "Capacidade", "Ocupação", "Ociosidade", "Vagas livres"],
                    linhas, [0.12, 0.16, 0.12, 0.15, 0.15, 0.15, 0.15], centralizadas=range(1, 7))
    conteudo.titulo("Qualidade da distribuição")
    conteudo.texto("Equilíbrio entre turmas: maior diferença de tamanho dentro do mesmo turno.", 9)
    conteudo.tabela(["Turno", "Diferença entre as turmas"], [
        [turno.title(), texto_diferenca_turmas(dados["alunos"]["amplitude"])]
        for turno, dados in metricas["balanceamento"].items()
    ], [0.3, 0.7])
    variacao = metricas["destaques"]["variacao_genero"]
    conteudo.texto(f"Maior variação H/M: {texto_variacao_genero(variacao)}", 10, QFont.Weight.Medium, AZUL)
    if variacao["quantidade"]:
        conteudo.texto("Turmas com maior variação: " + ", ".join(nome_turma_visual(t) for t in variacao["turmas"]), 9)

    conteudo.titulo("Gráficos do dashboard", nova_pagina=True)
    turmas = metricas["turmas"]
    if not turmas:
        conteudo.texto("Nenhuma turma disponível para representar nos gráficos.")
    for por_sexo in (False, True):
        partes = ceil(len(turmas) / 10)
        for inicio in range(0, len(turmas), 10):
            imagem, altura = _grafico(turmas[inicio:inicio + 10], turmas, conteudo.largura, por_sexo, inicio // 10 + 1, partes)
            conteudo.imagem(imagem, altura)

    conteudo.titulo("Inconsistências e avisos", nova_pagina=True)
    inconsistencias, avisos = separar_ocorrencias(resultado)
    for titulo, registros, descricao, cor, fundo, vazio in (
        ("Inconsistências", inconsistencias, "Registros não alocados que precisam de revisão manual.",
         ALERTA, FUNDO_ALERTA, "Nenhuma inconsistência encontrada."),
        ("Avisos", avisos, "Normalizações automáticas e registros mantidos válidos, sem bloqueio cadastral.",
         AZUL, FUNDO_AZUL, "Nenhum aviso gerado."),
    ):
        conteudo.texto(f"{titulo} · {len(registros)}", 12, QFont.Weight.Medium, cor, 5)
        conteudo.texto(descricao, 9, cor=TEXTO_SECUNDARIO)
        if registros:
            conteudo.tabela(["Linha(s)", "Aluno / registro", "Motivo"],
                            [[r["Linha"], r["Nome"], r["Motivo"]] for r in registros],
                            [0.12, 0.29, 0.59], cor=cor, fundo=fundo)
        else:
            conteudo.texto(vazio, 9, cor=TEXTO_SECUNDARIO, depois=14)

    conteudo.titulo("Anexo · Alunos por turma", nova_pagina=True)
    conteudo.texto("Listagem completa da distribuição, independentemente dos filtros da tela. Nomes repetidos são preservados como registros distintos.", 9, cor=TEXTO_SECUNDARIO, depois=12)
    for indice, turma in enumerate(turmas):
        if indice:
            conteudo.texto("Alunos por turma · continuação do anexo", 10, QFont.Weight.Medium, AZUL, nova_pagina=True)
        identificacao = (f"Turma {turma['nome']} · Turno: {turma['turno'].title()}\n"
                         f"Alunos: {turma['total_alunos']} / {turma['capacidade']} vagas · Ocupação: {formatar_percentual(turma['taxa_ocupacao'])}")
        alunos = resultado.grupos[turma["nome"]]
        linhas = [[i, r["Nome"], {"F": "Feminino", "M": "Masculino"}.get(r["Sexo"], r["Sexo"]),
                   str(r["Disponibilidade"]).title()] for i, r in enumerate(alunos, 1)]
        conteudo.tabela(["Nº", "Aluno", "Sexo", "Disponibilidade"],
                        linhas or [["—", "Nenhum aluno nesta turma.", "—", "—"]],
                        [0.07, 0.53, 0.19, 0.21], centralizadas=(0,), identificacao=identificacao, padding=4)
    sem_turma = metricas["nao_alocados"]["alunos"]
    if sem_turma:
        conteudo.titulo("Anexo · Alunos sem turma", nova_pagina=True)
        conteudo.texto("Alunos válidos que permaneceram sem turma no resultado existente.", 9)
        conteudo.tabela(["Nº", "Aluno", "Sexo", "Disponibilidade"], [
            [i, r["nome"], {"F": "Feminino", "M": "Masculino"}.get(r["sexo"], r["sexo"]), r["disponibilidade"].title()]
            for i, r in enumerate(sem_turma, 1)
        ], [0.07, 0.53, 0.19, 0.21], centralizadas=(0,), identificacao=f"Sem turma · {len(sem_turma)} alunos", padding=4)


def _escrever_pdf(resultado, destino, execucao):
    arquivo = QFile(str(destino))
    if not arquivo.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(arquivo.errorString())
    writer = QPdfWriter(arquivo)
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Point)
    writer.setTitle(f"Relatório de distribuição — {resultado.origem.name}")
    writer.setCreator("ABC Aprendiz — Sistema de Ensalamento")
    largura, altura = writer.width(), writer.height()
    margem, topo, rodape = 42, 90, 40
    corpo_largura, corpo_altura = largura - 2 * margem, altura - topo - rodape
    conteudo = None
    pintor = QPainter()
    try:
        conteudo = _Conteudo(corpo_largura, corpo_altura, writer)
        _montar_conteudo(conteudo, resultado, execucao, datetime.now().astimezone())
        paginas = conteudo.doc.pageCount()
        logo = QImage(str(caminho_recurso("assets", "logo_abc_aprendiz.png")))
        if not pintor.begin(writer):
            raise OSError("Não foi possível iniciar a gravação do PDF.")
        for pagina in range(paginas):
            if pagina and not writer.newPage():
                raise OSError("Não foi possível gravar uma página do relatório PDF.")
            if not logo.isNull():
                pintor.drawImage(QRectF(margem, 25, 32 * logo.width() / logo.height(), 32), logo)
            pintor.setFont(_fonte(10, QFont.Weight.Medium))
            pintor.setPen(QColor(AZUL))
            pintor.drawText(QRectF(largura - margem - 300, 25, 300, 18), Qt.AlignmentFlag.AlignRight, "Relatório de ensalamento")
            pintor.setFont(_fonte(8))
            pintor.setPen(QColor(TEXTO_SECUNDARIO))
            nome = pintor.fontMetrics().elidedText(resultado.origem.name, Qt.TextElideMode.ElideMiddle, 300)
            pintor.drawText(QRectF(largura - margem - 300, 44, 300, 14), Qt.AlignmentFlag.AlignRight, nome)
            for inicio, proporcao, cor in ((0, 0.8, AZUL), (0.8, 0.15, TURQUESA), (0.95, 0.05, VERDE)):
                pintor.fillRect(QRectF(margem + corpo_largura * inicio, 71, corpo_largura * proporcao, 2), QColor(cor))
            pintor.save()
            pintor.translate(margem, topo - pagina * corpo_altura)
            conteudo.doc.drawContents(pintor, QRectF(0, pagina * corpo_altura, corpo_largura, corpo_altura))
            pintor.restore()
            pintor.setPen(QPen(QColor(BORDA), 0.5))
            pintor.drawLine(QRectF(margem, altura - 29, corpo_largura, 0).topLeft(), QRectF(margem, altura - 29, corpo_largura, 0).topRight())
            pintor.setFont(_fonte(8))
            pintor.setPen(QColor(TEXTO_SECUNDARIO))
            pintor.drawText(QRectF(margem, altura - 22, corpo_largura, 14), Qt.AlignmentFlag.AlignLeft,
                            f"ABC Aprendiz · Execução {execucao.codigo}")
            pintor.drawText(QRectF(margem, altura - 22, corpo_largura, 14), Qt.AlignmentFlag.AlignRight,
                            f"Página {pagina + 1} de {paginas}")
        if not pintor.end():
            raise OSError("Não foi possível finalizar o relatório PDF.")
        # Libera o dispositivo antes de substituir o destino, inclusive no Windows.
        conteudo = None
        writer = None
        if not arquivo.flush():
            raise OSError(arquivo.errorString())
    finally:
        if pintor.isActive():
            pintor.end()
        conteudo = None
        writer = None
        arquivo.close()


def exportar_relatorio_pdf(resultado: ResultadoInterface, destino: Path,
                          execucao: IdentificacaoExecucao | None = None) -> Path:
    """Não lê nem grava XLSX, não recalcula métricas e não chama o solver."""
    destino = Path(destino).resolve()
    if destino.suffix.lower() != ".pdf":
        raise ValueError("Escolha um arquivo com a extensão .pdf para o relatório.")
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(prefix="abc_relatorio_", suffix=".pdf", dir=destino.parent, delete=False) as arquivo:
            temporario = Path(arquivo.name)
        _escrever_pdf(resultado, temporario, execucao or IdentificacaoExecucao())
        os.replace(temporario, destino)
    except PermissionError as erro:
        raise PermissionError("Feche o relatório PDF, verifique a permissão da pasta ou escolha outro destino.") from erro
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
    return destino

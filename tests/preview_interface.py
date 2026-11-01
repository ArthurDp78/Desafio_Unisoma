"""Renderiza a UI em modo offscreen, sem controlar a área de trabalho."""
import os
from pathlib import Path
import sys
from statistics import median
from time import perf_counter

os.environ["QT_QPA_PLATFORM"] = "offscreen"
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from apresentacao import processar_planilha
from interface_desktop import JanelaPrincipal, LARGURA_DASHBOARD_DESKTOP
from tema import fonte_interface


def main():
    pasta = Path(sys.argv[1])
    pasta.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    # O plugin offscreen não enumera as fontes do Windows automaticamente.
    for nome in ("segoeui.ttf", "segoeuib.ttf", "segoeuisl.ttf"):
        fonte = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / nome
        if fonte.exists():
            QFontDatabase.addApplicationFont(str(fonte))
    app.setStyle("Fusion")
    app.setPalette(app.style().standardPalette())
    app.setFont(fonte_interface())
    janela = JanelaPrincipal()
    janela.resize(LARGURA_DASHBOARD_DESKTOP + 80, 820)
    origem = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "Dados" / "instancia_1.xlsx"
    janela.definir_arquivo(origem)
    janela.mostrar_resultado(processar_planilha(origem))
    janela.show()
    for indice, nome in enumerate(("dashboard", "alunos", "ocorrencias")):
        janela.mudar_secao(indice)
        QTest.qWait(160)
        assert janela.grab().save(str(pasta / f"{nome}.png"))
    janela.mudar_secao(0)
    janela.resize(1920, 1080)
    QTest.qWait(160)
    assert janela.grab().save(str(pasta / "dashboard_full_hd.png"))
    janela.resize(1366, 768)
    QTest.qWait(160)
    janela.dashboard.verticalScrollBar().setValue(0)
    assert janela.grab().save(str(pasta / "dashboard_1366_768.png"))
    janela.dashboard.verticalScrollBar().setValue(janela.dashboard.verticalScrollBar().maximum())
    QTest.qWait(160)
    assert janela.grab().save(str(pasta / "dashboard_1366_768_resumos.png"))
    janela.dashboard.verticalScrollBar().setValue(0)
    janela.mudar_secao(2)
    QTest.qWait(160)
    assert janela.grab().save(str(pasta / "ocorrencias_1366_768.png"))
    janela.mudar_secao(0)
    janela.resize(880, 600)
    QTest.qWait(160)
    janela.dashboard.verticalScrollBar().setValue(0)
    assert janela.grab().save(str(pasta / "dashboard_compacto.png"))
    janela.dashboard_proximo.click()
    QTest.qWait(160)
    assert janela.grab().save(str(pasta / "dashboard_compacto_sexos.png"))
    tempos = []
    for i in range(60):
        inicio = perf_counter()
        janela.mudar_secao(i % janela.secoes.count())
        app.processEvents()
        tempos.append((perf_counter() - inicio) * 1000)
        QTest.qWait(4)
    QTest.qWait(160)
    print(f"Troca de seção (60 operações locais, incluindo pintura): mediana {median(tempos):.2f} ms; máximo {max(tempos):.2f} ms")
    janela.mudar_secao(0)
    janela.resize(1366, 768)
    # Dados exclusivamente visuais para revisar a rolagem interna com muitas turmas.
    for grafico in janela.graficos:
        grafico.definir({f"Turma {i + 1:02}": (12, 15) if grafico.por_sexo else 27
                         for i in range(40)})
    QTest.qWait(160)
    janela.dashboard.verticalScrollBar().setValue(0)
    for area in janela.areas_graficos:
        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
    QTest.qWait(160)
    assert janela.grab().save(str(pasta / "graficos_rolados_1366_768.png"))
    janela.close()
    print(f"Prévias gravadas em {pasta}")


if __name__ == "__main__":
    main()

"""Renderiza a UI em modo offscreen, sem controlar a área de trabalho."""
import os
from pathlib import Path
import sys
from statistics import median
from time import perf_counter

os.environ["QT_QPA_PLATFORM"] = "offscreen"
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from apresentacao import processar_planilha
from interface_desktop import JanelaPrincipal


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
    app.setFont(QFont("Segoe UI", 10))
    janela = JanelaPrincipal()
    janela.resize(1180, 820)
    origem = RAIZ / "Dados" / "instancia_1.xlsx"
    janela.definir_arquivo(origem)
    janela.mostrar_resultado(processar_planilha(origem))
    janela.show()
    for indice, nome in enumerate(("dashboard", "alunos", "inconsistencias")):
        janela.mudar_secao(indice)
        QTest.qWait(160)
        assert janela.grab().save(str(pasta / f"{nome}.png"))
    janela.mudar_secao(0)
    janela.mudar_dashboard(1)
    QTest.qWait(160)
    assert janela.grab().save(str(pasta / "dashboard_sexos.png"))
    tempos = []
    for i in range(60):
        inicio = perf_counter()
        janela.mudar_secao(i % 3)
        app.processEvents()
        tempos.append((perf_counter() - inicio) * 1000)
        QTest.qWait(4)
    QTest.qWait(160)
    print(f"Troca de seção (60 operações locais, incluindo pintura): mediana {median(tempos):.2f} ms; máximo {max(tempos):.2f} ms")
    janela.close()
    print(f"Prévias gravadas em {pasta}")


if __name__ == "__main__":
    main()

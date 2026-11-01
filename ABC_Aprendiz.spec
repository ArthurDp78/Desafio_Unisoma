# Executável único: inclui o aplicativo, o Qt, os recursos e o CBC do PuLP no .exe.
from PyInstaller.utils.hooks import collect_data_files
from pathlib import Path

a = Analysis(
    ['ensalamento.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=collect_data_files('pulp', includes=['solverdir/cbc/win/i64/*'])
          + [(str(Path(SPECPATH) / 'assets'), 'assets')],
    hiddenimports=['openpyxl', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
                   'PySide6.QtSvg', 'PySide6.QtSvgWidgets'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtQml', 'PySide6.QtQuick', 'matplotlib', 'IPython', 'pytest'],
    noarchive=False,
)
# O Qt para Windows usa a API ICU do próprio Windows. Uma ICU de outro
# programa no PATH pode ser coletada com o mesmo nome e sem os símbolos
# esperados, causando "DLL load failed" antes da abertura da janela.
a.binaries = [entrada for entrada in a.binaries
              if Path(entrada[0]).name.lower() != 'icuuc.dll'
              and not Path(entrada[0]).name.lower().startswith('icudt')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='ABC_Aprendiz',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)

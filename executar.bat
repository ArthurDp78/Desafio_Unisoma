@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0dist\ABC_Aprendiz.exe" (
    start "ABC Aprendiz" "%~dp0dist\ABC_Aprendiz.exe"
    exit /b
)
if exist "%~dp0.venv-ui\Scripts\python.exe" (
    "%~dp0.venv-ui\Scripts\python.exe" "%~dp0ensalamento.py"
    if errorlevel 1 pause
    exit /b
)
py -3.12 -c "import pandas, pulp, openpyxl; import PySide6.QtWidgets" >nul 2>&1
if not errorlevel 1 (
    py -3.12 "%~dp0ensalamento.py"
    if errorlevel 1 pause
    exit /b
)
python -c "import pandas, pulp, openpyxl; import PySide6.QtWidgets" >nul 2>&1
if not errorlevel 1 (
    python "%~dp0ensalamento.py"
    if errorlevel 1 pause
    exit /b
)
echo Nao foi encontrado um Python com as dependencias da aplicacao.
echo Consulte a instalacao no README.md.
pause
exit /b 1

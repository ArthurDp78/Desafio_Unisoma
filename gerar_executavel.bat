@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv-ui\Scripts\python.exe" (
    "%~dp0.venv-ui\Scripts\python.exe" -m PyInstaller --noconfirm ABC_Aprendiz.spec
) else (
    py -3.12 -m PyInstaller --noconfirm ABC_Aprendiz.spec
)
if errorlevel 1 (
    echo Falha ao gerar o executavel. Instale requirements-dev.txt e tente novamente.
    pause
    exit /b 1
)
echo Executavel gerado em dist\ABC_Aprendiz\ABC_Aprendiz.exe
echo Distribua a pasta ABC_Aprendiz inteira, incluindo a pasta _internal.

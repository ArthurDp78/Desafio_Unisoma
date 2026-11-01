@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_BUILD_ARGS="
if exist "%~dp0.venv-ui\Scripts\python.exe" (
    set "PYTHON_BUILD=%~dp0.venv-ui\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_BUILD=%~dp0.venv\Scripts\python.exe"
) else (
    set "PYTHON_BUILD=py"
    set "PYTHON_BUILD_ARGS=-3.12"
)
"%PYTHON_BUILD%" %PYTHON_BUILD_ARGS% -m playwright install chromium --only-shell
if errorlevel 1 (
    echo Falha ao preparar o gerador do manual. Instale requirements-dev.txt e tente novamente.
    pause
    exit /b 1
)
"%PYTHON_BUILD%" %PYTHON_BUILD_ARGS% -m PyInstaller --noconfirm ABC_Aprendiz.spec
if errorlevel 1 (
    echo Falha ao gerar o executavel. Instale requirements-dev.txt e tente novamente.
    pause
    exit /b 1
)
echo Executavel unico gerado em dist\ABC_Aprendiz.exe
echo Manual gerado em dist\Manual_do_Usuario_ABC_Aprendiz.pdf
echo Distribua o executavel e o manual juntos, na mesma pasta.

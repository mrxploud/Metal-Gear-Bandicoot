@echo off
rem Metal Gear Bandicoot: dois cliques aqui abrem o teste mais novo (ou o disco que voce montou).
rem Opcoes do motor\jogar.py tambem valem aqui: JOGAR.bat --dock (direto no Loading Dock), --menu, --disco ...
cd /d "%~dp0"
if exist "motor\.venv\Scripts\python.exe" (
    "motor\.venv\Scripts\python.exe" -I motor\jogar.py %*
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Precisa do Python 3.12 instalado: veja "Como rodar" no README.md.
        pause
        exit /b 1
    )
    python -I motor\jogar.py %*
)
if errorlevel 1 pause

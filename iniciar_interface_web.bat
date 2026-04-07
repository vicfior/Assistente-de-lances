@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo Crie primeiro com: python -m venv .venv
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
streamlit run app.py

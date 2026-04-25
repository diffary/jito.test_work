@echo off
REM Launch the accounting demo. Double-click or run from cmd / PowerShell.
cd /d "%~dp0"

if not exist ".venv\Scripts\streamlit.exe" (
    echo [run.bat] Virtualenv not found. Creating .venv and installing requirements...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo [run.bat] ERROR: failed to install requirements.
        pause
        exit /b 1
    )
)

echo [run.bat] Starting Streamlit on http://localhost:8501 ...
.venv\Scripts\streamlit.exe run app\ui\main.py

@echo off
set VENV_DIR=venv

if not exist %VENV_DIR% (
    echo Creating virtual environment...
    python -m venv %VENV_DIR%
)

call %VENV_DIR%\Scripts\activate.bat

if exist requirements.txt (
    echo Installing requirements...
    pip install -r requirements.txt
)

echo Starting SmartFactoryLogger...
python src/main.py
pause

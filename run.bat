@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 正在初始化环境...
    python -m venv .venv
    call .venv\Scripts\pip install -r requirements.txt -q
)
call .venv\Scripts\activate
python main.py

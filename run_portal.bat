@echo off
cd /d "%~dp0"
echo Installing dependencies...
python -m pip install -r requirements.txt
echo.
echo Starting CBSE Question Bank Builder...
echo Open http://127.0.0.1:8000 in your browser.
python app\server.py

@echo off
echo Starting K-town Python Server...
cd /d "%~dp0"
python -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
@echo off
chcp 65001 >nul
echo ====================================================================
echo   DATAMIND AI AGENT STUDIO - HE THONG PHAN TICH DU LIEU TU HANH
echo ====================================================================
echo.

set PYTHON_CMD=python
if exist "%USERPROFILE%\.local\bin\python3.12.exe" (
    set PYTHON_CMD="%USERPROFILE%\.local\bin\python3.12.exe"
)

echo [1/2] Dang khoi dong may chu AI Agent tai http://127.0.0.1:8050 ...
start "" http://127.0.0.1:8050
%PYTHON_CMD% app.py
pause

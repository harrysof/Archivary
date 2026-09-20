@echo off
rem Launch Archivary without a console window using the project's venv.
setlocal
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "run.py"
endlocal

@echo off
echo ============================================================
echo Running DCRG Backend Test Suite
echo ============================================================
cd /d "%~dp0\..\backend"
call .venv\Scripts\activate.bat
python -m pytest tests -v
cd /d "%~dp0\..\frontend"
echo ============================================================
echo Building DCRG Frontend (Type and Bundle Validation)
echo ============================================================
call npm.cmd run build

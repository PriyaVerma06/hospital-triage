@echo off
REM =============================================================================
REM scripts\start.bat - One-command startup for the Hospital Triage System
REM Windows
REM
REM Usage:
REM   scripts\start.bat
REM
REM Ctrl+C stops both backend and frontend.
REM =============================================================================

setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0.."
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

echo.
echo [triage] Hospital Triage System - Windows startup
echo.

REM ── Prerequisite checks ───────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is required. Install from https://python.org
    exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is required. Install from https://nodejs.org
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm is required. Install Node.js from https://nodejs.org
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f %%v in ('node --version') do set NODE_VER=%%v
echo [triage] Python %PY_VER% ^| Node %NODE_VER%

REM ── Backend: virtual environment ──────────────────────────────────────────
if not exist "%BACKEND_DIR%\.venv" (
    echo [triage] Creating Python virtual environment ...
    python -m venv "%BACKEND_DIR%\.venv"
)

set "PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "PIP=%BACKEND_DIR%\.venv\Scripts\pip.exe"

echo [triage] Checking Python dependencies ...
"%PIP%" install -q -r "%BACKEND_DIR%\requirements.txt"

REM ── Backend: seed database if missing ─────────────────────────────────────
if not exist "%BACKEND_DIR%\triage.db" (
    echo [triage] No triage.db found - seeding initial data ...
    pushd "%BACKEND_DIR%"
    "%PYTHON%" seed.py
    popd
)

REM ── Frontend: install node_modules if missing ─────────────────────────────
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [triage] Installing frontend dependencies ...
    pushd "%FRONTEND_DIR%"
    npm install
    popd
)

REM ── Print startup banner ──────────────────────────────────────────────────
echo.
echo ================================================================
echo   Hospital Triage System - starting services
echo ================================================================
echo.
echo   Backend  -^>  http://127.0.0.1:8000
echo   Frontend -^>  http://localhost:5173
echo   API Docs -^>  http://127.0.0.1:8000/docs
echo.
echo   Demo accounts (password: demo123):
echo     admin    - full access
echo     nurse1   - patient intake and queue
echo     dr1-dr5  - doctor dashboard and alerts
echo.
echo   Close this window (or Ctrl+C) to stop both services.
echo ================================================================
echo.

REM ── Start backend in a new window ─────────────────────────────────────────
echo [triage] Starting FastAPI backend ...
start "Triage Backend" cmd /k "cd /d %BACKEND_DIR% && .venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"

REM Give uvicorn a moment to start
timeout /t 2 /nobreak >nul

REM ── Start frontend in a new window ────────────────────────────────────────
echo [triage] Starting Vite dev server ...
start "Triage Frontend" cmd /k "cd /d %FRONTEND_DIR% && npm run dev"

echo.
echo [triage] Both services started in separate windows.
echo [triage] Close those windows to stop them.
echo.
pause
endlocal

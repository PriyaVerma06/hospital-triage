#!/usr/bin/env bash
# =============================================================================
# scripts/start.sh – One-command startup for the Hospital Triage System
# macOS / Linux
#
# Usage:
#   chmod +x scripts/start.sh
#   ./scripts/start.sh
#
# Ctrl+C stops both backend and frontend.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# ── Colour helpers ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[triage]${NC} $*"; }
warn()  { echo -e "${YELLOW}[triage]${NC} $*"; }
error() { echo -e "${RED}[triage]${NC} $*"; exit 1; }

# ── Prerequisite checks ──────────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || error "Python 3 is required. Install from https://python.org"
command -v node    >/dev/null 2>&1 || error "Node.js is required. Install from https://nodejs.org"
command -v npm     >/dev/null 2>&1 || error "npm is required. Install Node.js from https://nodejs.org"

PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
NODE_VERSION=$(node --version)
info "Python $PY_VERSION | Node $NODE_VERSION"

# ── Require JWT secret ───────────────────────────────────────────────────────
if [ -z "${TRIAGE_SECRET_KEY:-}" ] || [ "${#TRIAGE_SECRET_KEY}" -lt 32 ]; then
    error "Set TRIAGE_SECRET_KEY to a random value of at least 32 characters before startup."
fi

# ── Backend: virtual environment ─────────────────────────────────────────────
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    info "Creating Python virtual environment at backend/.venv …"
    python3 -m venv "$BACKEND_DIR/.venv"
fi

PYTHON="$BACKEND_DIR/.venv/bin/python"
PIP="$BACKEND_DIR/.venv/bin/pip"

info "Checking Python dependencies …"
"$PIP" install -q -r "$BACKEND_DIR/requirements.txt"

# ── Backend: initialize schema (no sample hospital data is inserted) ────────
info "Initializing database schema …"
(cd "$BACKEND_DIR" && "$PYTHON" seed.py)

# ── Frontend: install node_modules if missing ────────────────────────────────
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    info "Installing frontend dependencies (npm install) …"
    (cd "$FRONTEND_DIR" && npm install)
fi

# ── Print startup banner ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Hospital Triage System – starting services               ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Backend  →  http://127.0.0.1:8000"
echo "  Frontend →  http://localhost:5173"
echo "  API Docs →  http://127.0.0.1:8000/docs"
echo ""
echo "  Sign-in is restricted to provisioned clinical staff (NURSE / DOCTOR)."
echo ""
echo "  Ctrl+C to stop both services."
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""

# ── Cleanup handler ──────────────────────────────────────────────────────────
cleanup() {
    info "Shutting down …"
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    info "Done."
}
trap cleanup INT TERM

# ── Start backend ────────────────────────────────────────────────────────────
info "Starting FastAPI backend …"
(cd "$BACKEND_DIR" && "$PYTHON" -m uvicorn main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

# Give uvicorn a moment to start
sleep 2

# ── Start frontend ───────────────────────────────────────────────────────────
info "Starting Vite dev server …"
(cd "$FRONTEND_DIR" && npm run dev) &
FRONTEND_PID=$!

# ── Wait ─────────────────────────────────────────────────────────────────────
wait "$BACKEND_PID" "$FRONTEND_PID"

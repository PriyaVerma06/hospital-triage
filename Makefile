# Makefile – Hospital Triage System shortcuts
# Usage: make <target>

.PHONY: start reset-demo scenario test test-backend test-frontend test-smoke help

# ── Startup ──────────────────────────────────────────────────────────────────
start:                        ## Start backend + frontend together (macOS/Linux)
	bash scripts/start.sh

# ── Demo tooling ─────────────────────────────────────────────────────────────
reset-demo:                   ## Reset database to clean state (seed only, no patients)
	cd backend && .venv/bin/python demo.py reset

scenario:                     ## Run scripted patient scenario (normal speed)
	cd backend && .venv/bin/python demo.py scenario

scenario-fast:                ## Run scripted patient scenario (fast speed)
	cd backend && .venv/bin/python demo.py scenario --speed fast

# ── Tests ────────────────────────────────────────────────────────────────────
test-backend:                 ## Run backend pytest suite
	cd backend && .venv/bin/pytest tests/ -v

test-frontend:                ## Run frontend unit tests (vitest)
	cd frontend && npm test

test-smoke:                   ## Run E2E smoke test (requires running server)
	cd backend && .venv/bin/python ../tests_e2e/smoke_test.py

test: test-backend test-frontend ## Run all unit tests (backend + frontend)

# ── Build ────────────────────────────────────────────────────────────────────
build:                        ## Build frontend production bundle
	cd frontend && npm run build

# ── Help ─────────────────────────────────────────────────────────────────────
help:                         ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

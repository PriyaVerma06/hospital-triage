# Hospital Triage System developer commands

.PHONY: start init-db create-staff create-bed migrate-demo-data test test-backend test-frontend test-smoke build help

start: ## Start backend + frontend together (macOS/Linux)
	bash scripts/start.sh

init-db: ## Create schema and remove legacy demo login accounts
	cd backend && .venv/bin/python seed.py

create-staff: ## Provision a real NURSE or DOCTOR account
	cd backend && .venv/bin/python create_staff.py

create-bed: ## Add one real hospital bed
	cd backend && .venv/bin/python create_bed.py

migrate-demo-data: ## Safely migrate an older database away from unused demo resources
	cd backend && .venv/bin/python migrate_demo_resources.py

test-backend: ## Run backend pytest suite
	cd backend && .venv/bin/pytest tests/ -v

test-frontend: ## Run frontend unit tests
	cd frontend && npm test

test-smoke: ## Run E2E smoke test (requires provisioned clinical test accounts)
	cd backend && .venv/bin/python ../tests_e2e/smoke_test.py

test: test-backend test-frontend ## Run all unit tests

build: ## Build frontend production bundle
	cd frontend && npm run build

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\\n", $$1, $$2}'

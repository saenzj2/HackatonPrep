# Guardians of the Harvest — task runner.
# Every target runs inside backend/ using the venv binaries directly,
# so you never need to "activate" anything.

BACKEND := backend
VENV    := $(BACKEND)/.venv
BIN     := $(CURDIR)/$(VENV)/bin

# First Python >= 3.11 found on PATH. Override with: make setup PYTHON=/path/to/python3.12
PYTHON ?= $(shell for p in python3.13 python3.12 python3.11 python3; do \
	command -v $$p >/dev/null 2>&1 && $$p -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null \
	&& { command -v $$p; break; }; done)

FAST := -m "not slow and not network"

.DEFAULT_GOAL := help
.PHONY: help setup install hooks dev test test-all lint fmt check clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: install hooks ## First-time setup: venv + deps + git hooks

install: ## Create backend/.venv and install the backend with dev deps
	@if [ -z "$(PYTHON)" ]; then \
		echo "ERROR: Python >= 3.11 not found. Install it (macOS: brew install python@3.12)"; \
		echo "       or pass it explicitly: make setup PYTHON=/path/to/python3.12"; exit 1; fi
	@$(PYTHON) -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { \
		echo "ERROR: $(PYTHON) is $$($(PYTHON) --version 2>&1); Python >= 3.11 is required."; exit 1; }
	@echo "Using $(PYTHON) ($$($(PYTHON) --version))"
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --quiet --upgrade pip
	cd $(BACKEND) && $(BIN)/pip install --quiet -e ".[dev]"
	@test -f $(BACKEND)/.env || cp $(BACKEND)/.env.example $(BACKEND)/.env
	@echo "Done. Next: make dev"

hooks: ## Install pre-commit git hooks
	$(BIN)/pre-commit install

dev: ## Run the API with auto-reload on http://localhost:8000 (docs at /docs)
	cd $(BACKEND) && $(BIN)/uvicorn app.main:create_app --factory --reload --port 8000

test: ## Fast tests (no network, no slow)
	cd $(BACKEND) && $(BIN)/pytest -q $(FAST)

test-all: ## All tests, including slow and real-network ones
	cd $(BACKEND) && $(BIN)/pytest -q

lint: ## Lint + format check + type check (no changes)
	cd $(BACKEND) && $(BIN)/ruff check . && $(BIN)/ruff format --check . && $(BIN)/mypy

fmt: ## Auto-fix lint and format
	cd $(BACKEND) && $(BIN)/ruff format . && $(BIN)/ruff check --fix .

check: lint test ## Everything CI runs (contract tests are part of `test`)

clean: ## Remove venv and caches
	rm -rf $(VENV) $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache
	find $(BACKEND) -name __pycache__ -type d -prune -exec rm -r {} +

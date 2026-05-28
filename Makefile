# ── Configuracao ──────────────────────────────────────────────────────────────
VENV         := .dbt-env
PYTHON       := $(VENV)/Scripts/python
PIP          := $(VENV)/Scripts/pip
DBT          := $(VENV)/Scripts/dbt
PROFILES_DIR := $(CURDIR)/dbt_project
DBT_CMD      := DBT_PROFILES_DIR=$(PROFILES_DIR) DUCKDB_PATH=$(CURDIR)/data/financial_dw.duckdb $(DBT)

# ── Setup ─────────────────────────────────────────────────────────────────────
.PHONY: setup
setup:
	@if [ ! -d "$(VENV)" ]; then python -m venv $(VENV); fi
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt
	$(VENV)/Scripts/pre-commit install
	mkdir -p data
	@echo "Setup concluido. Ative o venv: source $(VENV)/Scripts/activate"

# ── Ingestao ──────────────────────────────────────────────────────────────────
.PHONY: ingest
ingest:
	$(PYTHON) ingestion/generate_calendar.py
	$(PYTHON) ingestion/ingest_bacen.py
	$(PYTHON) ingestion/ingest_market.py

# ── dbt ───────────────────────────────────────────────────────────────────────
.PHONY: deps seed build test docs fix
deps:
	$(DBT_CMD) deps --project-dir dbt_project

seed:
	$(DBT_CMD) seed --project-dir dbt_project

build:
	$(DBT_CMD) build --project-dir dbt_project

test:
	$(DBT_CMD) test --project-dir dbt_project

docs:
	$(DBT_CMD) docs generate --project-dir dbt_project
	$(DBT_CMD) docs serve --project-dir dbt_project

fix:
	DBT_PROFILES_DIR=$(PROFILES_DIR) DUCKDB_PATH=$(CURDIR)/data/financial_dw.duckdb \
	$(VENV)/Scripts/sqlfluff fix dbt_project/models dbt_project/snapshots \
	--dialect duckdb --templater dbt

# ── Pipeline completo ─────────────────────────────────────────────────────────
.PHONY: all
all: ingest seed build

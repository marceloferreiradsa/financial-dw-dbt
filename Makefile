# ── Configuração ──────────────────────────────────────────────────────────────
VENV        := .dbt-env
PYTHON      := $(VENV)/Scripts/python
PIP         := $(VENV)/Scripts/pip
DBT         := $(VENV)/Scripts/dbt
PROFILES_DIR := $(CURDIR)/dbt_project

# ── Setup ─────────────────────────────────────────────────────────────────────
.PHONY: setup
setup:
	@if [ ! -d "$(VENV)" ]; then python -m venv $(VENV); fi
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt
	$(VENV)/Scripts/pre-commit install
	mkdir -p data
	@echo "Setup concluido. Ative o venv: source $(VENV)/Scripts/activate"

# ── Ingestão ──────────────────────────────────────────────────────────────────
.PHONY: ingest
ingest:
	$(PYTHON) ingestion/generate_calendar.py
	$(PYTHON) ingestion/ingest_bacen.py
	$(PYTHON) ingestion/ingest_market.py

# ── dbt ───────────────────────────────────────────────────────────────────────
.PHONY: deps seed build test docs
deps:
	DBT_PROFILES_DIR=$(PROFILES_DIR) $(DBT) deps --project-dir dbt_project

seed:
	DBT_PROFILES_DIR=$(PROFILES_DIR) $(DBT) seed --project-dir dbt_project

build:
	DBT_PROFILES_DIR=$(PROFILES_DIR) $(DBT) build --project-dir dbt_project

test:
	DBT_PROFILES_DIR=$(PROFILES_DIR) $(DBT) test --project-dir dbt_project

docs:
	DBT_PROFILES_DIR=$(PROFILES_DIR) $(DBT) docs generate --project-dir dbt_project
	DBT_PROFILES_DIR=$(PROFILES_DIR) $(DBT) docs serve --project-dir dbt_project

# ── Pipeline completo ─────────────────────────────────────────────────────────
.PHONY: all
all: ingest seed build

.PHONY: fix
fix:
	DBT_PROFILES_DIR=$(PROFILES_DIR) $(VENV)/Scripts/sqlfluff fix dbt_project/models dbt_project/snapshots --dialect duckdb --templater dbt

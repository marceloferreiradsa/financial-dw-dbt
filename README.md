# Financial Data Warehouse — dbt + DuckDB

> **Portfolio Project** | dbt Core com dados reais da API BACEN e B3, orquestrado com Apache Airflow

[![dbt CI](https://github.com/marceloferreiradsa/financial-dw-dbt/actions/workflows/ci.yml/badge.svg)](https://github.com/marceloferreiradsa/financial-dw-dbt/actions)
[![dbt Docs](https://img.shields.io/badge/dbt%20docs-GitHub%20Pages-blue)](https://marceloferreiradsa.github.io/financial-dw-dbt)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## O que este projeto demonstra

### dbt

| Feature | Arquivo |
|---|---|
| Arquitetura 3 camadas (staging → intermediate → marts) | `dbt_project/models/` |
| `sources.yml` com freshness checks | `models/staging/sources.yml` |
| Incremental model com `merge` strategy | `marts/market/mart_stock_performance.sql` |
| Snapshot SCD Type 2 (`strategy: check`) | `snapshots/snap_ticker_metadata.sql` |
| Testes com `dbt_utils` + `dbt_expectations` | `schema.yml` em cada camada |
| Macro Jinja parametrizada | `macros/calculate_rolling_metrics.sql` |
| Override de `generate_schema_name` | `macros/generate_schema_name.sql` |
| Seed com tipagem explicita | `seeds/dim_calendar.csv` |
| CI com `state:modified+` | `.github/workflows/ci.yml` |
| dbt Docs no GitHub Pages | `.github/workflows/docs.yml` |
| SQL lint (sqlfluff) no pre-commit e CI | `.sqlfluff`, `.pre-commit-config.yaml` |

### Engenharia

| Feature | Arquivo |
|---|---|
| Ingestao de dados macroeconomicos via API BACEN | `ingestion/ingest_bacen.py` |
| Ingestao de cotacoes B3 via Brapi (brapi.dev) | `ingestion/ingest_market.py` |
| Orquestracao com Apache Airflow + Docker Compose | `orchestration/` |
| Pipeline automatizado via Makefile | `Makefile` |
| pre-commit hooks (trailing whitespace, YAML, sqlfluff) | `.pre-commit-config.yaml` |

---

## Arquitetura

```
API SGS/BACEN  →  raw.bacen_series
Brapi/B3       →  raw.market_prices
                        │
                   STAGING (views)
              stg_bacen_series | stg_market_prices
                        │
                INTERMEDIATE (tables)
           int_macro_pivoted | int_market_returns
                        │
                  MARTS (table/incremental)
     finance/mart_macro_indicators | market/mart_stock_performance
                        │
                   SNAPSHOTS
              snap_ticker_metadata (SCD Type 2)
```

---

## Setup

### Pre-requisitos

- Python 3.11+
- Git
- `make`
  - **WSL / Linux / Mac:** ja disponivel nativamente
  - **Windows (Git Bash):** `winget install GnuWin32.Make` e adicionar ao PATH:
    `echo 'export PATH=$PATH:"/c/Program Files (x86)/GnuWin32/bin"' >> ~/.bashrc`

### 1. Clone o repositorio

```bash
git clone https://github.com/marceloferreiradsa/financial-dw-dbt.git
cd financial-dw-dbt
```

### 2. Configure o ambiente

```bash
make setup
source .dbt-env/Scripts/activate   # Windows/Git Bash
# source .dbt-env/bin/activate      # WSL/Linux/Mac
```

### 3. Configure as variaveis de ambiente

```bash
cp .env.example .env
# Os valores padrao ja funcionam — nenhuma edicao necessaria
```

### 4. Rode a ingestao de dados

```bash
make ingest
```

Busca series macroeconomicas do BACEN (Selic, IPCA, CDI, USD/BRL, IGP-M, juro real)
e cotacoes historicas de 4 tickers B3 via Brapi — **sem necessidade de token ou cadastro**.

### 5. Execute o pipeline dbt

```bash
make build
```

### 6. Visualize a documentacao

```bash
make docs
# Acesse: http://localhost:8080
```

### Pipeline completo (ingestao + dbt)

```bash
make all
```

---

## Comandos disponiveis

| Comando | O que faz |
|---|---|
| `make setup` | Cria o venv e instala todas as dependencias |
| `make ingest` | Roda os tres scripts de ingestao |
| `make deps` | Instala os pacotes dbt (`packages.yml`) |
| `make seed` | Carrega o seed `dim_calendar` |
| `make build` | Roda `dbt build` (seed + models + tests) |
| `make test` | Roda apenas os testes dbt |
| `make docs` | Gera e serve a documentacao dbt |
| `make fix` | Auto-corrige violacoes de estilo SQL via sqlfluff |
| `make all` | Ingestao + seed + build completo |

---

## GitHub Pages (dbt Docs automatico)

Ative o GitHub Pages no repositorio:
`Settings → Pages → Source: GitHub Actions`

Apos cada push em `main`, os docs sao publicados automaticamente em:
`https://marceloferreiradsa.github.io/financial-dw-dbt`

---

## Estrutura

```
financial-dw-dbt/
├── .github/workflows/      ci.yml, docs.yml
├── .vscode/                extensions.json
├── dbt_project/
│   ├── models/
│   │   ├── staging/        sources.yml, schema.yml, stg_*.sql
│   │   ├── intermediate/   int_*.sql
│   │   └── marts/          finance/, market/ (incremental)
│   ├── snapshots/          snap_ticker_metadata.sql
│   ├── macros/             generate_schema_name.sql, calculate_rolling_metrics.sql
│   ├── seeds/              dim_calendar.csv
│   ├── dbt_project.yml
│   ├── packages.yml
│   └── profiles.yml
├── ingestion/              ingest_bacen.py, ingest_market.py, generate_calendar.py
├── orchestration/
│   ├── dags/               financial_pipeline.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements-airflow.txt
│   └── .env.airflow.example
├── .env.example
├── .gitattributes
├── .gitignore
├── .pre-commit-config.yaml
├── .sqlfluff
├── Makefile
├── requirements.txt
├── CHANGELOG.md
└── README.md
```

---

## Pacotes dbt

| Pacote | Uso |
|---|---|
| `dbt-labs/dbt_utils ^1.3` | `unique_combination_of_columns`, date_spine |
| `metaplane/dbt_expectations ^0.10` | `expect_column_values_to_be_between` |
| `dbt-labs/audit_helper ^0.12` | Validacao de refactoring |
| `dbt-labs/codegen ^0.12` | Geracao automatica de YAML |

---

## Licenca

MIT — [LICENSE](LICENSE)

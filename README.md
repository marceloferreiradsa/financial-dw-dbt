# Financial Data Warehouse — dbt + DuckDB

> **Portfolio Project 1** | dbt Core intermediário/avançado com dados reais da API BACEN e B3

[![dbt CI](https://github.com/SEU_USUARIO/financial-dw-dbt/actions/workflows/ci.yml/badge.svg)](https://github.com/SEU_USUARIO/financial-dw-dbt/actions)
[![dbt Docs](https://img.shields.io/badge/dbt%20docs-GitHub%20Pages-blue)](https://SEU_USUARIO.github.io/financial-dw-dbt)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features dbt demonstradas

| Feature | Arquivo |
|---|---|
| Arquitetura 3 camadas (staging → intermediate → marts) | `models/` |
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

---

## Arquitetura

```
API SGS/BACEN  →  raw.bacen_series
yfinance/B3    →  raw.market_prices
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

## Setup (Windows)

### Prerequisitos
- Python 3.11 ou 3.12
- Git
- VSCode + extensao [dbt Power User](https://marketplace.visualstudio.com/items?itemName=innoverio.vscode-dbt-power-user)

### 1. Clone e configure

```bat
git clone https://github.com/SEU_USUARIO/financial-dw-dbt.git
cd financial-dw-dbt
setup_venv.bat
```

### 2. Configure variaveis de ambiente

```bat
copy .env.example .env
:: Edite o .env com DUCKDB_PATH, BACEN_START_DATE, TICKERS
```

### 3. Configure profiles.yml

```bat
copy dbt_project\profiles.yml %USERPROFILE%\.dbt\profiles.yml
:: OU: set DBT_PROFILES_DIR=%CD%\dbt_project
```

### 4. Rode a ingestao de dados

```bat
.venv\Scripts\activate.bat
python ingestion/generate_calendar.py
python ingestion/ingest_bacen.py
python ingestion/ingest_market.py
```

### 5. Execute o pipeline dbt

```bat
cd dbt_project
dbt deps
dbt seed
dbt build
```

### 6. Visualize a documentacao

```bat
dbt docs generate
dbt docs serve
:: Acesse: http://localhost:8080
```

---

## GitHub Pages (dbt Docs automatico)

Ative o GitHub Pages no repositorio:
`Settings → Pages → Source: GitHub Actions`

Apos cada push em `main`, os docs sao publicados automaticamente.

---

## Estrutura

```
financial-dw-dbt/
├── .github/workflows/    ci.yml, docs.yml
├── .vscode/              extensions.json
├── dbt_project/
│   ├── models/
│   │   ├── staging/      sources.yml, schema.yml, stg_*.sql
│   │   ├── intermediate/ int_*.sql
│   │   └── marts/        finance/, market/ (incremental)
│   ├── snapshots/        snap_ticker_metadata.sql
│   ├── macros/           generate_schema_name.sql, calculate_rolling_metrics.sql
│   ├── seeds/            dim_calendar.csv
│   ├── dbt_project.yml
│   ├── packages.yml
│   └── profiles.yml      (nao versionado — copiar para ~/.dbt/)
├── ingestion/            ingest_bacen.py, ingest_market.py, generate_calendar.py
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .sqlfluff
├── requirements.txt
├── setup_venv.bat
├── CHANGELOG.md
└── README.md
```

---

## Pacotes dbt

| Pacote | Uso |
|---|---|
| `dbt-labs/dbt_utils ^1.3` | `surrogate_key`, `unique_combination_of_columns`, date_spine |
| `calogica/dbt_expectations ^0.10` | `expect_column_values_to_be_between` |
| `dbt-labs/audit_helper ^0.12` | Validacao de refactoring |
| `dbt-labs/codegen ^0.12` | Geracao automatica de YAML |

---

## Licenca

MIT — [LICENSE](LICENSE)

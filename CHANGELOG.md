# Changelog

## [1.1.0] - 2026-05-28

### Changed
- Substituida fonte de dados de mercado: yfinance → Brapi (brapi.dev)
  - Elimina rate limit agressivo do Yahoo Finance
  - 4 tickers gratuitos sem necessidade de token: PETR4, MGLU3, VALE3, ITUB4
  - Qualquer pessoa pode replicar o projeto sem cadastro
- TICKERS no .env atualizado para remover sufixo .SA (formato Brapi)
- profiles.yml adicionado ao versionamento (usa apenas env_var, sem credenciais)

### Fixed
- ingest_market.py: corrigida ordem de reset_index() antes do rename de colunas
- ingest_market.py: substituido datetime.utcnow() por datetime.now(timezone.utc)
- ingest_bacen.py: substituido datetime.utcnow() por datetime.now(timezone.utc)
- schema.yml: corrigido posicionamento do teste unique_combination_of_columns
  (movido de nivel de coluna para nivel de modelo)
- pre-commit: adicionado dbt-core e dbt-duckdb como additional_dependencies
  do hook sqlfluff para resolver erro de adapter nao encontrado
- pre-commit: corrigida versao inexistente pre-commit==3.8.2 → 3.8.0

### Added
- Makefile: automatiza setup, ingestao e comandos dbt
- .gitattributes: normaliza line endings entre Windows e Linux/Mac
- make fix: target para auto-correcao de violacoes sqlfluff

## [1.0.0] - 2025-05-09

### Added
- Setup inicial: dbt-core 1.9.4 + dbt-duckdb
- Camada staging: stg_bacen_series, stg_market_prices
- Camada intermediate: int_macro_pivoted, int_market_returns
- Marts: mart_macro_indicators, mart_stock_performance (incremental/merge)
- Snapshot SCD Type 2: snap_ticker_metadata
- Seed: dim_calendar (2019-2030)
- Macros: generate_schema_name, calculate_rolling_metrics
- Scripts de ingestao: BACEN SGS API, yfinance B3, generate_calendar
- CI/CD: GitHub Actions (compile, build state:modified+, sqlfluff, docs deploy)
- pre-commit hooks: trailing-whitespace, check-yaml, sqlfluff

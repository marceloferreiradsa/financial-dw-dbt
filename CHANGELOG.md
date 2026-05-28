# Changelog

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

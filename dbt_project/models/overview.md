{% docs __overview__ %}

# Financial Data Warehouse — dbt + DuckDB

Pipeline de dados financeiros brasileiros construido com dbt Core, DuckDB e Apache Airflow.
Ingere series macroeconomicas do Banco Central e cotacoes de acoes da B3,
transformando dados brutos em indicadores prontos para consumo por dashboards e analises.

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
     mart_macro_indicators | mart_stock_performance
                        │
                   SNAPSHOTS
              snap_ticker_metadata (SCD Type 2)
```

## Camadas

**Staging** — Views. Cast de tipos, renomeacao para snake_case e filtros defensivos.
Sem logica de negocio. Uma linha por chave natural da fonte.

**Intermediate** — Tables. Transformacoes complexas reutilizaveis: pivot de series BACEN
de long para wide, calculo de retorno logaritmico e metricas de risco via window functions.

**Marts** — Tables e Incrementals. Produto final para consumo. Combinam dados de mercado
com contexto macroeconomico e expoe metricas derivadas como IPCA acumulado 12m,
volatilidade anualizada e premio de risco vs CDI.

## Fontes de dados

- **API SGS/BACEN** — Series macroeconomicas publicas: Selic, IPCA, CDI, USD/BRL, IGP-M, juro real
- **Brapi (brapi.dev)** — Cotacoes historicas B3: PETR4, MGLU3, VALE3, ITUB4

## Tecnologias

- **dbt Core 1.9** — Transformacoes SQL com testes, documentacao e lineage
- **DuckDB** — Banco de dados OLAP embarcado, sem servidor
- **Apache Airflow** — Orquestracao do pipeline (`orchestration/`)
- **GitHub Actions** — CI/CD com `state:modified+` e deploy automatico desta documentacao

{% enddocs %}

{% snapshot snap_ticker_metadata %}

{{
    config(
        target_schema='snapshots',
        strategy='check',
        unique_key='ticker',
        check_cols=['company_name', 'sector', 'market_index'],
        invalidate_hard_deletes=True
    )
}}

/*
    SCD Type 2: rastreia mudancas em metadados dos tickers.
    Captura: mudanca de razao social, reclassificacao de setor,
           entrada/saida de indices.

    dbt gera automaticamente:
    dbt_scd_id, dbt_valid_from, dbt_valid_to, dbt_updated_at, dbt_is_deleted
    */

    select distinct
        ticker,
        company_name,
        sector,
        market_index,
        current_timestamp as updated_at
    from {{ ref('stg_market_prices') }}

{% endsnapshot %}

{{
    config(
        materialized='view',
        tags=['staging', 'market']
    )
}}

/*
  Staging de cotacoes historicas B3.

  Decisao de design: log_return_daily e calculado aqui pois e uma
  transformacao matematica pura da serie de precos (nao e logica de negocio).
  adj_close e mantido separado de close para distinguir analises de
  retorno real (adj_close) de analises de preco nominal (close).
*/

with source as (

    select * from {{ source('raw_market', 'market_prices') }}

),

renamed as (

    select
        cast(ticker as varchar) as ticker,
        cast(company as varchar) as company_name,
        cast(sector as varchar) as sector,
        cast(market_index as varchar) as market_index,
        cast(date as date) as trade_date,
        cast(open as double) as price_open,
        cast(high as double) as price_high,
        cast(low as double) as price_low,
        cast(close as double) as price_close,
        cast(adj_close as double) as price_adj_close,
        cast(volume as bigint) as volume,
        cast(ingested_at as timestamp) as ingested_at,
        coalesce(cast(dividends as double), 0.0) as dividends,
        coalesce(cast(stock_splits as double), 0.0) as stock_splits

    from source
    where close is not null and close > 0

),

with_daily_return as (

    select
        *,

        -- Retorno logaritmico diario: ln(P_t / P_{t-1})
        -- Numericamente mais estavel que retorno aritmetico para series longas
        ln(
            price_adj_close / nullif(
                lag(price_adj_close) over (
                    partition by ticker
                    order by trade_date
                ), 0
            )
        ) as log_return_daily,

        coalesce(dividends > 0 or stock_splits != 0, false) as has_corporate_event

    from renamed

)

select * from with_daily_return

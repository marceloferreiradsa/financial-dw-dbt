{{
    config(
        materialized='table',
        tags=['intermediate', 'market']
    )
}}

/*
  Enriquece cotacoes com metricas de retorno e risco.
  Janelas: 21d (~1 mes), 63d (~1 trimestre), 252d (~1 ano).
*/

with prices as (
    select * from {{ ref('stg_market_prices') }}
),

with_metrics as (

    select
        ticker,
        company_name,
        sector,
        market_index,
        trade_date,
        price_open,
        price_high,
        price_low,
        price_close,
        price_adj_close,
        volume,
        dividends,
        has_corporate_event,
        log_return_daily,

        -- Retorno acumulado: exp(sum dos log_returns) desde o inicio da serie
        exp(
            sum(log_return_daily) over (
                partition by ticker
                order by trade_date
                rows between unbounded preceding and current row
            )
        ) as cumulative_return_index,

        -- Volatilidade realizada anualizada (21d)
        stddev(log_return_daily) over (
            partition by ticker
            order by trade_date
            rows between 20 preceding and current row
        ) * sqrt(252) as volatility_21d_annualized,

        -- Volatilidade realizada anualizada (63d)
        stddev(log_return_daily) over (
            partition by ticker
            order by trade_date
            rows between 62 preceding and current row
        ) * sqrt(252) as volatility_63d_annualized,

        -- Maximo historico acumulado (para calcular drawdown)
        max(price_adj_close) over (
            partition by ticker
            order by trade_date
            rows between unbounded preceding and current row
        ) as running_peak,

        -- Drawdown: queda percentual em relacao ao pico historico
        (
            price_adj_close / nullif(
                max(price_adj_close) over (
                    partition by ticker
                    order by trade_date
                    rows between unbounded preceding and current row
                ), 0
            ) - 1
        ) as drawdown_from_peak,

        -- Volume medio 21d para detectar anomalias de liquidez
        avg(volume) over (
            partition by ticker
            order by trade_date
            rows between 20 preceding and current row
        ) as avg_volume_21d

    from prices
    where log_return_daily is not null

)

select * from with_metrics

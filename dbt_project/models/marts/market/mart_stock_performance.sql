{{
    config(
        materialized='incremental',
        unique_key=['ticker', 'trade_date'],
        incremental_strategy='merge',
        on_schema_change='append_new_columns',
        tags=['marts', 'market', 'incremental']
    )
}}

/*
  Mart principal de performance — ponto de consumo para dashboards/BI.

  Estrategia incremental:
    unique_key = (ticker, trade_date) identifica cada observacao unicamente.
    merge atualiza registros existentes (captura ajustes retroativos do Yahoo).
    Janela de 7 dias garante que splits/dividendos retroativos sejam capturados.
*/

with market_returns as (

    select * from {{ ref('int_market_returns') }}

    {% if is_incremental() %}
        where trade_date >= (
            select max(trade_date) - interval '7 days'
            from {{ this }}
        )
    {% endif %}

),

macro as (
    select * from {{ ref('int_macro_pivoted') }}
),

joined as (

    select
        -- Chaves
        mr.ticker,
        mr.trade_date,

        -- Dimensoes
        mr.company_name,
        mr.sector,
        mr.market_index,

        -- Precos
        mr.price_open,
        mr.price_high,
        mr.price_low,
        mr.price_close,
        mr.price_adj_close,
        mr.volume,
        mr.avg_volume_21d,
        mr.has_corporate_event,
        mr.dividends,

        -- Retornos e risco
        mr.log_return_daily,
        mr.cumulative_return_index,
        mr.volatility_21d_annualized,
        mr.volatility_63d_annualized,
        mr.drawdown_from_peak,
        mr.running_peak,

        -- Contexto macro
        mc.selic_rate,
        mc.usd_brl_rate,
        mc.cdi_rate,
        mc.ipca_monthly_pct,

        -- Premio de risco simplificado: volatilidade vs CDI
        mr.volatility_21d_annualized - (coalesce(mc.cdi_rate, 0) / 100) as risk_premium_vs_cdi,

        current_timestamp as dbt_updated_at

    from market_returns as mr
    left join macro as mc
        on mr.trade_date = mc.macro_date

)

select * from joined

{{
    config(
        materialized='table',
        tags=['marts', 'finance']
    )
}}

/*
  Mart de indicadores macroeconomicos consolidados.
  Adiciona IPCA acumulado 12m, variacao do cambio e juro real ex-post.
*/

with macro as (
    select * from {{ ref('int_macro_pivoted') }}
    where is_bacen_business_day = true
),

enriched as (

    select
        macro_date,
        selic_rate,
        usd_brl_rate,
        cdi_rate,
        ipca_monthly_pct,
        igpm_monthly_pct,
        real_interest_rate,
        is_bacen_business_day,

        -- IPCA acumulado 12 meses via produto de (1 + var_mensal/100)
        -- exp(sum(ln)) evita produto em janela (nao suportado em SQL puro)
        (exp(
            sum(ln(1 + coalesce(ipca_monthly_pct, 0) / 100)) over (
                order by macro_date
                rows between 364 preceding and current row
            )
        ) - 1) * 100 as ipca_accumulated_12m_pct,

        -- Variacao mensal do cambio (~21 dias uteis)
        (usd_brl_rate / nullif(
            lag(usd_brl_rate, 21) over (
                order by macro_date
            ), 0
        ) - 1) * 100 as usd_brl_monthly_change_pct,

        current_timestamp as dbt_updated_at

    from macro

)

select * from enriched
order by macro_date

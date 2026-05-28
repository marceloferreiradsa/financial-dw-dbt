{{
    config(
        materialized='table',
        tags=['intermediate', 'macroeconomic']
    )
}}

/*
  Pivota series BACEN de long para wide.
  Series mensais (IPCA, IGP-M) terao NULL em dias sem observacao -- intencional.
  Downstream usa forward fill quando necessario.
*/

with daily_series as (
    select * from {{ ref('stg_bacen_series') }}
    where frequency = 'daily'
),

monthly_series as (
    select * from {{ ref('stg_bacen_series') }}
    where frequency = 'monthly'
),

date_spine as (
    select distinct reference_date as macro_date
    from daily_series
),

daily_pivot as (
    select
        reference_date as macro_date,
        max(case when series_name = 'selic_rate' then series_value end) as selic_rate,
        max(case when series_name = 'usd_brl_rate' then series_value end) as usd_brl_rate,
        max(case when series_name = 'cdi_rate' then series_value end) as cdi_rate
    from daily_series
    group by reference_date
),

monthly_pivot as (
    select
        date_trunc('month', reference_date)::date as month_date,
        max(case when series_name = 'ipca_inflation' then series_value end) as ipca_monthly_pct,
        max(case when series_name = 'igpm_inflation' then series_value end) as igpm_monthly_pct,
        max(case when series_name = 'real_interest_rate' then series_value end) as real_interest_rate
    from monthly_series
    group by date_trunc('month', reference_date)::date
),

joined as (
    select
        ds.macro_date,
        dp.selic_rate,
        dp.usd_brl_rate,
        dp.cdi_rate,
        mp.ipca_monthly_pct,
        mp.igpm_monthly_pct,
        mp.real_interest_rate,
        -- Dias sem selic sao feriados/fins de semana no BACEN
        dp.selic_rate is not null as is_bacen_business_day
    from date_spine as ds
    left join daily_pivot as dp
        on ds.macro_date = dp.macro_date
    left join monthly_pivot as mp
        on date_trunc('month', ds.macro_date)::date = mp.month_date
)

select * from joined
order by macro_date

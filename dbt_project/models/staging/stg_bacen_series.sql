{{
    config(
        materialized='view',
        tags=['staging', 'macroeconomic']
    )
}}

/*
  Staging de series macroeconomicas BACEN.
  Responsabilidades:
    1. Cast explicito de tipos
    2. Rename para snake_case padronizado
    3. Filtro defensivo de nulos e valores invalidos
    4. SEM logica de negocio — isso fica nas camadas downstream
*/

with source as (

    select * from {{ source('raw_bacen', 'bacen_series') }}

),

renamed as (

    select
        cast(series_code as integer) as series_code,
        cast(series_name as varchar) as series_name,
        cast(frequency as varchar) as frequency,
        cast(unit as varchar) as unit,
        cast(date as date) as reference_date,
        cast(value as double) as series_value,
        cast(ingested_at as timestamp) as ingested_at

    from source

),

validated as (

    select *
    from renamed
    where
        reference_date is not null
        and series_value is not null
        -- Taxas de juros e cambio nao podem ser zero ou negativos
        and not (
            series_name in ('usd_brl_rate', 'selic_rate', 'cdi_rate')
            and series_value <= 0
        )

)

select * from validated

/*
  Macro reutilizavel para metricas rolling window.

  Uso no modelo SQL:
    select
        ticker,
        trade_date,
        {{ calculate_rolling_metrics(
            metric_col='log_return_daily',
            partition_col='ticker',
            order_col='trade_date',
            windows=[21, 63, 252],
            aggregations=['avg', 'stddev']
        ) }}
    from {{ ref('stg_market_prices') }}

  Gera colunas: avg_log_return_daily_21d, stddev_log_return_daily_21d, etc.
*/
{% macro calculate_rolling_metrics(metric_col, partition_col, order_col, windows, aggregations) %}

    {% for window in windows %}
        {% for agg in aggregations %}
    {{ agg }}({{ metric_col }}) over (
        partition by {{ partition_col }}
        order by {{ order_col }}
        rows between {{ window - 1 }} preceding and current row
    ) as {{ agg }}_{{ metric_col }}_{{ window }}d
            {%- if not loop.last %},{% endif %}
        {% endfor %}
        {%- if not loop.last %},{% endif %}
    {% endfor %}

{% endmacro %}

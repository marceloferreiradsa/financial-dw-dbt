/*
  Override do macro padrao do dbt para geracao de schema names.

  Comportamento padrao dbt: <target_schema>_<custom_schema>  (ex: dbt_marcelo_staging)
  Nosso comportamento:
    - dev:  <target_schema>_<custom_schema>  (isolamento por desenvolvedor)
    - prod: <custom_schema> exato             (sem prefixo — schema limpo no prod)

  Isso evita que dois devs sobrescrevam os mesmos schemas ao rodar localmente.
*/
{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {%- if custom_schema_name is none -%}
        {{ default_schema }}

    {%- elif target.name == 'prod' -%}
        {{ custom_schema_name | trim }}

    {%- else -%}
        {{ default_schema }}_{{ custom_schema_name | trim }}

    {%- endif -%}

{%- endmacro %}

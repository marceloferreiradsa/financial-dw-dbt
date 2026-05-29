# Estendemos a imagem oficial do Airflow em vez de partir do zero.
# Isso garante que todos os entrypoints, scripts de inicializacao
# e configuracoes padrao do Airflow estejam presentes.
FROM apache/airflow:2.9.3-python3.11

USER airflow

# Garante que o diretorio de dados existe com permissao do usuario airflow
# antes do volume Docker ser montado sobre ele
RUN mkdir -p /opt/airflow/data

# Dependencias do Airflow (Cosmos + providers) — sem dbt
COPY requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir -r /requirements-airflow.txt

# Venv isolado para dbt + dependencias dos scripts de ingestao.
# Separado do Airflow para evitar conflitos de dependencia — abordagem
# recomendada pela documentacao do Astronomer Cosmos.
RUN python -m venv /home/airflow/dbt-env && \
    /home/airflow/dbt-env/bin/pip install --no-cache-dir \
    dbt-core==1.9.4 \
    dbt-duckdb==1.9.2 \
    requests>=2.32.3 \
    pandas==2.2.3 \
    python-dotenv==1.0.1

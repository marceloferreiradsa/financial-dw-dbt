# Estendemos a imagem oficial do Airflow em vez de partir do zero.
# Isso garante que todos os entrypoints, scripts de inicialização
# e configurações padrão do Airflow estejam presentes.
FROM apache/airflow:2.9.3-python3.11

# Instalamos dependências como o usuário 'airflow' (não root).
# A imagem oficial recomenda isso explicitamente para evitar
# problemas de permissão em runtime.
USER airflow

COPY requirements-airflow.txt /requirements-airflow.txt

RUN pip install --no-cache-dir -r /requirements-airflow.txt

"""
DAG: financial_pipeline
=======================
Orquestra o pipeline completo de dados financeiros:

  1. ingest_bacen   -- API SGS/BACEN -> raw.bacen_series (DuckDB)
  2. ingest_market  -- Brapi/B3      -> raw.market_prices (DuckDB)
  3. dbt_seed       -- carrega dim_calendar no DuckDB
  4. dbt_transformations -- todos os modelos dbt com task-level observability (Cosmos)
  5. dbt_snapshot   -- SCD Type 2 em snap_ticker_metadata

Dependencias:
  ingest_bacen ---+
                  +---> dbt_seed ---> dbt_transformations ---> dbt_snapshot
  ingest_market --+

Ambas as ingestoes devem ter sucesso para o pipeline continuar.
Se qualquer task falhar, as tasks downstream sao marcadas como 'upstream_failed'
e o Airflow nao as executa -- evitando transformacoes sobre dados incompletos.
"""

import logging
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from airflow.decorators import dag
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig

log = logging.getLogger(__name__)

# -- Paths (resolvidos via env vars injetadas pelo docker-compose) -------------
DBT_PROJECT_DIR  = Path(os.getenv("DBT_PROJECT_DIR",  "/opt/airflow/dbt_project"))
DBT_PROFILES_DIR = DBT_PROJECT_DIR
INGESTION_DIR    = Path("/opt/airflow/ingestion")
DUCKDB_PATH      = Path(os.getenv("DUCKDB_PATH", "/opt/airflow/data/financial_dw.duckdb"))

# dbt e scripts de ingestao rodam no venv isolado para evitar
# conflitos de dependencia com o Airflow (recomendacao Astronomer Cosmos)
DBT_ENV_DIR      = Path("/home/airflow/dbt-env")
DBT_EXECUTABLE   = DBT_ENV_DIR / "bin" / "dbt"
DBT_ENV_PYTHON   = DBT_ENV_DIR / "bin" / "python"

# -- Argumentos padrao aplicados a todas as tasks ------------------------------
DEFAULT_ARGS = {
    "owner": "marcelo",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": False,
}


# -- Funcoes auxiliares --------------------------------------------------------

def _run_ingestion_script(script_name: str) -> None:
    """
    Executa um script de ingestao como subprocess usando o Python
    do venv isolado (dbt-env), que contem requests, pandas, duckdb.

    Subprocess em vez de importlib porque o Airflow roda no seu proprio
    ambiente Python que nao tem as dependencias dos scripts de ingestao.
    """
    script_path = INGESTION_DIR / f"{script_name}.py"
    cmd = [str(DBT_ENV_PYTHON), str(script_path)]

    log.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        log.info(result.stdout)
    if result.stderr:
        log.warning(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed with exit code {result.returncode}"
        )


def _run_dbt_command(command: str) -> None:
    """
    Executa um comando dbt como subprocess usando o dbt do venv isolado.

    Usado para dbt seed e dbt snapshot -- operacoes que o Cosmos
    nao precisa decompor em tasks individuais.
    """
    cmd = [
        str(DBT_EXECUTABLE),
        *command.split(),
        "--project-dir", str(DBT_PROJECT_DIR),
        "--profiles-dir", str(DBT_PROFILES_DIR),
        "--no-use-colors",
    ]
    log.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        log.info(result.stdout)
    if result.stderr:
        log.warning(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"dbt {command} failed with exit code {result.returncode}"
        )


# -- DAG definition ------------------------------------------------------------

@dag(
    dag_id="financial_pipeline",
    description="BACEN + B3 ingestion -> dbt transformations pipeline",
    # Dias uteis as 7h (apos fechamento da B3 do dia anterior)
    schedule="0 7 * * 1-5",
    start_date=days_ago(1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["financial", "dbt", "bacen", "b3"],
    max_active_runs=1,
    doc_md=__doc__,
)
def financial_pipeline():

    # -- 1. Ingestao BACEN -----------------------------------------------------
    ingest_bacen = PythonOperator(
        task_id="ingest_bacen",
        python_callable=_run_ingestion_script,
        op_args=["ingest_bacen"],
        doc_md="""
        **ingest_bacen**

        Consome a API publica SGS/BACEN e carrega series macroeconomicas
        no schema `raw` do DuckDB via INSERT OR REPLACE (idempotente).

        Series: Selic, IPCA, USD/BRL, IGP-M, CDI, Juro Real.

        Em caso de falha: retenta 2x com backoff exponencial (5min, 10min).
        """,
    )

    # -- 2. Ingestao B3 --------------------------------------------------------
    ingest_market = PythonOperator(
        task_id="ingest_market",
        python_callable=_run_ingestion_script,
        op_args=["ingest_market"],
        doc_md="""
        **ingest_market**

        Baixa cotacoes OHLCV diarias via Brapi (brapi.dev) e carrega em
        `raw.market_prices` (INSERT OR REPLACE -- idempotente).

        Tickers configurados via variavel de ambiente TICKERS.
        Tier gratuito: PETR4, MGLU3, VALE3, ITUB4.

        Roda em paralelo com ingest_bacen -- ambos devem ter sucesso
        antes das transformacoes dbt iniciarem.
        """,
    )

    # -- 3. dbt seed -----------------------------------------------------------
    dbt_seed = PythonOperator(
        task_id="dbt_seed",
        python_callable=_run_dbt_command,
        op_args=["seed"],
        doc_md="""
        **dbt_seed**

        Carrega arquivos CSV da pasta `seeds/` no DuckDB.
        Principal seed: `dim_calendar` (calendario 2019-2030).
        """,
    )

    # -- 4. dbt transformations via Cosmos -------------------------------------
    dbt_transformations = DbtTaskGroup(
        group_id="dbt_transformations",

        project_config=ProjectConfig(
            dbt_project_path=DBT_PROJECT_DIR,
            manifest_path=DBT_PROJECT_DIR / "target" / "manifest.json",
        ),

        profile_config=ProfileConfig(
            profile_name="financial_dw",
            target_name="dev",
            profiles_yml_filepath=DBT_PROFILES_DIR / "profiles.yml",
        ),

        execution_config=ExecutionConfig(
            dbt_executable_path=str(DBT_EXECUTABLE),
        ),

        operator_args={
            "install_deps": True,
            "full_refresh": False,
        },
    )

    # -- 5. dbt snapshot -------------------------------------------------------
    dbt_snapshot = PythonOperator(
        task_id="dbt_snapshot",
        python_callable=_run_dbt_command,
        op_args=["snapshot"],
        doc_md="""
        **dbt_snapshot**

        Executa snapshots SCD Type 2 apos todas as transformacoes.
        Captura mudancas em metadados de tickers (setor, nome, indice).
        """,
    )

    # -- Grafo de dependencias -------------------------------------------------
    [ingest_bacen, ingest_market] >> dbt_seed >> dbt_transformations >> dbt_snapshot


financial_pipeline()

"""
DAG: financial_pipeline
=======================
Orquestra o pipeline completo de dados financeiros:

  1. ingest_bacen   — API SGS/BACEN → raw.bacen_series (DuckDB)
  2. ingest_market  — yfinance/B3   → raw.market_prices (DuckDB)
  3. dbt_seed       — carrega dim_calendar no DuckDB
  4. dbt_transformations — todos os modelos dbt com task-level observability (Cosmos)
  5. dbt_snapshot   — SCD Type 2 em snap_ticker_metadata

Dependências:
  ingest_bacen ──┐
                 ├──► dbt_seed ──► dbt_transformations ──► dbt_snapshot
  ingest_market ──┘

Ambas as ingestões devem ter sucesso para o pipeline continuar.
Se qualquer task falhar, as tasks downstream são marcadas como 'upstream_failed'
e o Airflow não as executa — evitando transformações sobre dados incompletos.
"""

import importlib
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig
from cosmos.profiles import DuckDBUserPasswordProfileMapping

log = logging.getLogger(__name__)

# ── Paths (resolvidos via env vars injetadas pelo docker-compose) ─────────────
DBT_PROJECT_DIR  = Path(os.getenv("DBT_PROJECT_DIR",  "/opt/airflow/dbt_project"))
DBT_PROFILES_DIR = DBT_PROJECT_DIR
INGESTION_DIR    = Path("/opt/airflow/ingestion")
DUCKDB_PATH      = Path(os.getenv("DUCKDB_PATH", "/opt/airflow/data/financial_dw.duckdb"))
DBT_EXECUTABLE   = Path("/home/airflow/.local/bin/dbt")

# ── Argumentos padrão aplicados a todas as tasks ─────────────────────────────
DEFAULT_ARGS = {
    "owner": "marcelo",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    # Backoff exponencial: 1ª retry em 5min, 2ª em 10min
    # Evita sobrecarregar a API do BACEN em caso de instabilidade
    "retry_exponential_backoff": True,
    "email_on_failure": False,
}


# ── Funções auxiliares ────────────────────────────────────────────────────────

def _run_ingestion_script(script_name: str) -> None:
    """
    Importa dinamicamente e executa o main() de um script de ingestão.

    Por que importlib em vez de subprocess?
    - Reutiliza o processo Python já iniciado (sem overhead de fork)
    - Exceções propagam naturalmente → task falha corretamente no Airflow
    - Sem risco de shell injection
    - Logs aparecem diretamente no log da task
    """
    if str(INGESTION_DIR) not in sys.path:
        sys.path.insert(0, str(INGESTION_DIR))

    log.info(f"Importing and running {script_name}.main()")
    module = importlib.import_module(script_name)

    # Recarrega o módulo se já foi importado antes neste processo
    # (relevante em re-runs dentro da mesma sessão do scheduler)
    importlib.reload(module)
    module.main()
    log.info(f"{script_name}.main() completed successfully")


def _run_dbt_command(command: str) -> None:
    """
    Executa um comando dbt como subprocess.

    Usado para dbt seed e dbt snapshot — operações que o Cosmos
    não precisa decompor em tasks individuais.
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

    # Sempre loga stdout/stderr para aparecer no log da task
    if result.stdout:
        log.info(result.stdout)
    if result.stderr:
        log.warning(result.stderr)

    # Propaga o código de saída — task falha se dbt falhar
    if result.returncode != 0:
        raise RuntimeError(
            f"dbt {command} failed with exit code {result.returncode}"
        )


# ── DAG definition ────────────────────────────────────────────────────────────

@dag(
    dag_id="financial_pipeline",
    description="BACEN + B3 ingestion → dbt transformations pipeline",
    # Dias úteis às 7h (após fechamento da B3 do dia anterior)
    schedule="0 7 * * 1-5",
    start_date=days_ago(1),
    # catchup=False: não reprocessa execuções passadas perdidas
    # Para reprocessar histórico, use os scripts de ingestão diretamente
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["financial", "dbt", "bacen", "b3"],
    # Evita execuções paralelas do mesmo DAG (DuckDB não suporta múltiplos writers)
    max_active_runs=1,
    doc_md=__doc__,
)
def financial_pipeline():

    # ── 1. Ingestão BACEN ─────────────────────────────────────────────────────
    ingest_bacen = PythonOperator(
        task_id="ingest_bacen",
        python_callable=_run_ingestion_script,
        op_args=["ingest_bacen"],
        doc_md="""
        **ingest_bacen**

        Consome a API pública SGS/BACEN e carrega séries macroeconômicas
        no schema `raw` do DuckDB via INSERT OR REPLACE (idempotente).

        Séries: Selic, IPCA, USD/BRL, IGP-M, CDI, Juro Real.

        Em caso de falha: retenta 2x com backoff exponencial (5min, 10min).
        """,
    )

    # ── 2. Ingestão B3 ────────────────────────────────────────────────────────
    ingest_market = PythonOperator(
        task_id="ingest_market",
        python_callable=_run_ingestion_script,
        op_args=["ingest_market"],
        doc_md="""
        **ingest_market**

        Baixa cotações OHLCV diárias via yfinance e carrega em
        `raw.market_prices` (INSERT OR REPLACE — idempotente).

        Tickers configurados via variável de ambiente TICKERS.

        Roda em paralelo com ingest_bacen — ambos devem ter sucesso
        antes das transformações dbt iniciarem.
        """,
    )

    # ── 3. dbt seed ───────────────────────────────────────────────────────────
    # Seed antes do dbt_transformations porque int_macro_pivoted
    # pode fazer join com dim_calendar downstream
    dbt_seed = PythonOperator(
        task_id="dbt_seed",
        python_callable=_run_dbt_command,
        op_args=["seed"],
        doc_md="""
        **dbt_seed**

        Carrega arquivos CSV da pasta `seeds/` no DuckDB.
        Principal seed: `dim_calendar` (calendário 2019-2030 com feriados BR).
        """,
    )

    # ── 4. dbt transformations via Cosmos ─────────────────────────────────────
    # Cosmos lê o manifest.json e cria uma task Airflow por modelo dbt,
    # replicando as dependências do DAG dbt automaticamente.
    #
    # Para gerar o manifest antes do primeiro run:
    #   docker-compose exec airflow-scheduler \
    #     dbt compile --project-dir /opt/airflow/dbt_project \
    #                 --profiles-dir /opt/airflow/dbt_project
    dbt_transformations = DbtTaskGroup(
        group_id="dbt_transformations",

        # Onde está o projeto dbt e seu manifest compilado
        project_config=ProjectConfig(
            dbt_project_path=DBT_PROJECT_DIR,
            manifest_path=DBT_PROJECT_DIR / "target" / "manifest.json",
        ),

        # Como conectar ao DuckDB
        # Lê a Airflow Connection "duckdb_default" criada pelo airflow-init
        profile_config=ProfileConfig(
            profile_name="financial_dw",
            target_name="dev",
            profile_mapping=DuckDBUserPasswordProfileMapping(
                conn_id="duckdb_default",
                profile_args={"path": str(DUCKDB_PATH)},
            ),
        ),

        # Roda dbt como subprocess — mais compatível com todos os adapters
        execution_config=ExecutionConfig(
            dbt_executable_path=DBT_EXECUTABLE,
        ),

        operator_args={
            # Roda dbt deps automaticamente antes da primeira task
            "install_deps": True,
            # False = modo incremental (só processa dados novos)
            # Para full refresh manual: use a UI do Airflow → Trigger DAG w/ config
            "full_refresh": False,
        },
    )

    # ── 5. dbt snapshot ───────────────────────────────────────────────────────
    dbt_snapshot = PythonOperator(
        task_id="dbt_snapshot",
        python_callable=_run_dbt_command,
        op_args=["snapshot"],
        doc_md="""
        **dbt_snapshot**

        Executa snapshots SCD Type 2 após todas as transformações.
        Captura mudanças em metadados de tickers (setor, nome, índice).

        Roda por último para garantir que os dados dos marts já estão
        atualizados antes de capturar o estado atual.
        """,
    )

    # ── Grafo de dependências ─────────────────────────────────────────────────
    #
    # ingest_bacen ──┐
    #                ├──► dbt_seed ──► dbt_transformations ──► dbt_snapshot
    # ingest_market ──┘
    #
    # Se ingest_bacen OU ingest_market falhar:
    #   → dbt_seed não inicia
    #   → dbt_transformations não inicia
    #   → dbt_snapshot não inicia
    #   → todas as tasks downstream ficam marcadas como 'upstream_failed'
    #
    # Isso é o comportamento correto: transformações sobre dados incompletos
    # produziriam resultados silenciosamente errados.
    [ingest_bacen, ingest_market] >> dbt_seed >> dbt_transformations >> dbt_snapshot


# Airflow descobre DAGs importando o módulo — esta chamada em nível de
# módulo é obrigatória para o scheduler registrar o DAG
financial_pipeline()

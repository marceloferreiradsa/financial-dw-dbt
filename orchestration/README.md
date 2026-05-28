# Orchestration — Airflow + Cosmos

Orquestração do pipeline financeiro com Apache Airflow 2.9 e astronomer-cosmos.

## Arquitetura

```
ingest_bacen ──┐
               ├──► dbt_seed ──► dbt_transformations* ──► dbt_snapshot
ingest_market ──┘

* dbt_transformations: uma task Airflow por modelo dbt (via Cosmos)
  staging → intermediate → marts, respeitando o DAG do dbt
```

## Pré-requisitos

- Docker Desktop instalado e rodando
- Projeto `financial-dw-dbt` clonado localmente
- Esta pasta `orchestration/` dentro da raiz do projeto

## Setup

### 1. Configure as variáveis de ambiente

```bat
copy .env.airflow.example .env.airflow
```

Edite `.env.airflow` e gere as chaves:

```bat
:: Gere AIRFLOW_FERNET_KEY
.venv\Scripts\activate.bat
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

:: Gere AIRFLOW_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Build e inicialização (primeira vez)

```bat
cd orchestration

:: Build da imagem customizada + inicialização do metastore
docker-compose up airflow-init

:: Aguarde a mensagem "Init concluído." e então suba os serviços
docker-compose up -d airflow-webserver airflow-scheduler
```

### 3. Gere o manifest.json do dbt (necessário para o Cosmos)

O Cosmos lê o `manifest.json` para criar as tasks. Gere-o antes do primeiro run:

```bat
docker-compose exec airflow-scheduler \
  dbt compile \
  --project-dir /opt/airflow/dbt_project \
  --profiles-dir /opt/airflow/dbt_project
```

### 4. Acesse a UI

```
URL:   http://localhost:8080
User:  admin
Pass:  admin  (ou o valor definido em .env.airflow)
```

### 5. Trigger manual do pipeline

Na UI: DAGs → `financial_pipeline` → botão ▶ (Trigger DAG)

Ou via CLI:
```bat
docker-compose exec airflow-scheduler airflow dags trigger financial_pipeline
```

## Comandos úteis

```bat
:: Ver logs de uma task específica
docker-compose exec airflow-scheduler \
  airflow tasks logs financial_pipeline ingest_bacen <data_execucao>

:: Rodar uma task isolada (debug)
docker-compose exec airflow-scheduler \
  airflow tasks test financial_pipeline ingest_bacen 2025-01-01

:: Parar tudo (sem apagar dados)
docker-compose down

:: Parar e apagar TODOS os dados (DuckDB + Postgres metastore)
docker-compose down -v
```

## Estrutura

```
orchestration/
├── Dockerfile                  ← imagem customizada: airflow + dbt + cosmos
├── docker-compose.yml          ← postgres + airflow-init + webserver + scheduler
├── requirements-airflow.txt    ← dependências do container (separado do raiz)
├── .env.airflow.example        ← template de variáveis (versionado)
├── .env.airflow                ← valores reais (NÃO versionado)
└── dags/
    └── financial_pipeline.py   ← DAG principal com Cosmos TaskGroup
```

## Como o Cosmos funciona

1. `dbt compile` gera `dbt_project/target/manifest.json`
2. O Cosmos lê o manifest e encontra todos os nós do DAG dbt
3. Para cada nó (model, test, seed, snapshot) cria uma Airflow Task
4. Replica as dependências do dbt como dependências Airflow (`>>`)
5. Resultado: visibilidade por modelo na UI, não apenas por comando dbt

## Volumes Docker

| Volume | Tipo | Conteúdo | Perdido com `down -v`? |
|---|---|---|---|
| `duckdb-data` | Named volume | Banco DuckDB com todos os dados | ✅ Sim |
| `postgres-data` | Named volume | Metastore do Airflow | ✅ Sim |
| `../dbt_project` | Bind mount | Código dbt (editável no VSCode) | ❌ Não |
| `../ingestion` | Bind mount | Scripts Python de ingestão | ❌ Não |
| `./dags` | Bind mount | DAG files | ❌ Não |

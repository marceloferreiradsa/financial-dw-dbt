# Orchestration — Airflow + Cosmos

Orquestracao do pipeline financeiro com Apache Airflow 2.9 e astronomer-cosmos.

## Arquitetura

```
ingest_bacen ──┐
               ├──► dbt_seed ──► dbt_transformations* ──► dbt_snapshot
ingest_market ──┘

* dbt_transformations: uma task Airflow por modelo dbt (via Cosmos)
  staging → intermediate → marts, respeitando o DAG do dbt
```

## Pre-requisitos

- Docker Desktop instalado e rodando
- Projeto `financial-dw-dbt` clonado localmente
- Esta pasta `orchestration/` dentro da raiz do projeto

## Setup

### 1. Configure as variaveis de ambiente

```bash
cd orchestration
cp .env.airflow.example .env.airflow
```

Edite `.env.airflow` e gere as chaves (com o venv ativo na raiz do projeto):

```bash
# Gere AIRFLOW_FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Gere AIRFLOW_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Build e inicializacao (primeira vez)

```bash
cd orchestration

# Build da imagem customizada + inicializacao do metastore
docker compose up airflow-init

# Aguarde a mensagem "Init concluido." e entao suba os servicos
docker compose up -d airflow-webserver airflow-scheduler
```

### 3. Gere o manifest.json do dbt (necessario para o Cosmos)

O Cosmos le o `manifest.json` para criar as tasks. Gere-o antes do primeiro run:

```bash
docker compose exec airflow-scheduler \
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

Na UI: DAGs → `financial_pipeline` → botao ▶ (Trigger DAG)

Ou via CLI:

```bash
docker compose exec airflow-scheduler airflow dags trigger financial_pipeline
```

## Comandos uteis

```bash
# Ver logs de uma task especifica
docker compose exec airflow-scheduler \
  airflow tasks logs financial_pipeline ingest_bacen <data_execucao>

# Rodar uma task isolada (debug)
docker compose exec airflow-scheduler \
  airflow tasks test financial_pipeline ingest_bacen 2025-01-01

# Parar tudo (sem apagar dados)
docker compose down

# Parar e apagar TODOS os dados (DuckDB + Postgres metastore)
docker compose down -v
```

## Estrutura

```
orchestration/
├── Dockerfile                  ← imagem customizada: airflow + dbt + cosmos
├── docker-compose.yml          ← postgres + airflow-init + webserver + scheduler
├── requirements-airflow.txt    ← dependencias do container (separado do raiz)
├── .env.airflow.example        ← template de variaveis (versionado)
├── .env.airflow                ← valores reais (NAO versionado)
└── dags/
    └── financial_pipeline.py   ← DAG principal com Cosmos TaskGroup
```

## Como o Cosmos funciona

1. `dbt compile` gera `dbt_project/target/manifest.json`
2. O Cosmos le o manifest e encontra todos os nos do DAG dbt
3. Para cada no (model, test, seed, snapshot) cria uma Airflow Task
4. Replica as dependencias do dbt como dependencias Airflow (`>>`)
5. Resultado: visibilidade por modelo na UI, nao apenas por comando dbt

## Volumes Docker

| Volume | Tipo | Conteudo | Perdido com `down -v`? |
|---|---|---|---|
| `duckdb-data` | Named volume | Banco DuckDB com todos os dados | Sim |
| `postgres-data` | Named volume | Metastore do Airflow | Sim |
| `../dbt_project` | Bind mount | Codigo dbt (editavel no VSCode) | Nao |
| `../ingestion` | Bind mount | Scripts Python de ingestao | Nao |
| `./dags` | Bind mount | DAG files | Nao |

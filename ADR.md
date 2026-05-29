# Architecture Decision Records (ADR)

> Guia completo de decisoes tecnicas do projeto **Financial Data Warehouse**.
> Cada decisao documenta o contexto, alternativas avaliadas, escolha final e consequencias.
> Use como referencia para replicar, evoluir ou explicar o projeto.

---

## Ordem de implementacao

Se voce fosse reconstruir este projeto do zero, esta e a ordem correta:

```
1. Ambiente local (venv, .gitattributes, .gitignore)
2. Makefile
3. Pre-commit hooks + sqlfluff
4. Ingestao de dados (BACEN + mercado)
5. Pipeline dbt (staging -> intermediate -> marts)
6. Testes dbt (schema.yml em todas as camadas)
7. Snapshots (SCD Type 2)
8. CI/CD (GitHub Actions)
9. Documentacao (README, dbt docs, GitHub Pages)
10. Orquestracao (Airflow + Cosmos)
11. ADR (este documento)
```

Cada etapa depende da anterior. Nao pule — os erros mais comuns vem de
construir o pipeline antes de ter o linter configurado, ou configurar o
CI antes de ter os testes passando localmente.

---

## ADR-001: Virtual environment com nome customizado

**Contexto:** Python exige isolamento de dependencias por projeto.

**Alternativas:**
- `.venv` (convencao padrao)
- `.dbt-env` (nome descritivo)
- `poetry` / `pipenv` (gerenciadores alternativos)

**Decisao:** `.dbt-env` — identifica visualmente que o venv e para dbt,
util quando o desenvolvedor trabalha com multiplos projetos Python.

**Consequencia:** Makefile, `.gitignore` e README referenciam `.dbt-env`
em vez de `.venv`. Quem clonar precisa seguir o README.

---

## ADR-002: Makefile como interface de comandos

**Contexto:** O projeto tem muitos comandos (ingestao, dbt, sqlfluff, docs).
Memorizar cada um e impratico.

**Alternativas:**
- Scripts bash individuais
- `just` (alternativa moderna ao Make)
- Makefile

**Decisao:** Makefile — universal, disponivel em qualquer SO,
nao requer instalacao extra (exceto Windows, resolvido com GnuWin32).

**Targets criados:** `setup`, `ingest`, `deps`, `seed`, `build`, `test`,
`docs`, `fix`, `rebuild`, `all`.

**Consequencia:** Qualquer operacao do projeto e um `make <target>`.
O README documenta cada target com descricao.

---

## ADR-003: Pre-commit hooks com sqlfluff-lint

**Contexto:** Garantir qualidade de SQL antes do commit.

**Alternativas:**
- Lint so no CI (feedback tardio)
- Lint manual antes de commitar
- Pre-commit hooks (feedback imediato)

**Decisao:** Pre-commit com `sqlfluff-lint` usando templater `dbt`.
O hook roda automaticamente no `git commit`.

**Detalhe importante:** O hook `end-of-file-fixer` modifica arquivos mas
nao faz `git add` automaticamente. O ciclo correto e:
`git add` → `git commit` (hook corrige) → `git add` novamente → `git commit`.

**Dependencias no `.pre-commit-config.yaml`:**
```yaml
additional_dependencies:
  - sqlfluff-templater-dbt
  - dbt-core==1.9.4
  - dbt-duckdb==1.9.2
```

Sem essas dependencias, o templater dbt nao compila o projeto e o lint
falha silenciosamente.

---

## ADR-004: Brapi em vez de yfinance para dados de mercado

**Contexto:** O projeto precisa de cotacoes historicas de acoes brasileiras.

**Alternativas:**
- yfinance (Yahoo Finance) — popular, mas instavel com rate limiting agressivo
- Brapi (brapi.dev) — API brasileira, tier gratuito sem token para 4 tickers

**Decisao:** Brapi — confiavel, sem rate limiting no tier gratuito,
API REST simples, dados de B3 nativos.

**Tickers gratuitos:** PETR4, MGLU3, VALE3, ITUB4.

**Consequencia:** Qualquer pessoa pode replicar o projeto sem criar conta
ou obter token. O `.env.example` documenta os tickers padrao.

**Licao aprendida:** O yfinance usa sufixo `.SA` nos tickers (ex: `PETR4.SA`).
A Brapi nao usa. Ao migrar, os dados antigos com `.SA` persistiram no banco
como registros separados. A limpeza exigiu `--full-refresh` no modelo
incremental — o upsert nao substituiu porque as chaves primarias eram diferentes.

---

## ADR-005: DuckDB como data warehouse

**Contexto:** Projeto portfolio precisa de um banco analitico sem infraestrutura externa.

**Alternativas:**
- PostgreSQL (requer servidor rodando)
- SQLite (limitado para analytics)
- DuckDB (OLAP embutido, arquivo unico)
- Snowflake/BigQuery (custo, complexidade)

**Decisao:** DuckDB — zero infraestrutura, arquivo unico, SQL analitico
completo, adapter dbt maduro.

**Consequencia:** O banco e um unico arquivo em `data/financial_dw.duckdb`.
DuckDB so aceita um writer por vez — importante para a arquitetura do Airflow.

---

## ADR-006: Estrategia incremental delete+insert

**Contexto:** O modelo `mart_stock_performance` e incremental para
nao reprocessar todo o historico a cada run.

**Alternativas:**
- `merge` (Snowflake/BigQuery — nao suportado pelo DuckDB)
- `append` (duplica dados em re-runs)
- `delete+insert` (deleta o periodo e reinsere)

**Decisao:** `delete+insert` — unica estrategia incremental robusta
disponivel no dbt-duckdb.

**Consequencia:** O modelo usa `unique_key` e um lookback de 7 dias.
Em caso de mudanca radical nos dados fonte, `make rebuild` faz full-refresh.

---

## ADR-007: profiles.yml versionado no Git

**Contexto:** Convencao padrao e manter `profiles.yml` no `.gitignore`
porque normalmente contem credenciais.

**Alternativas:**
- Manter no `.gitignore` e gerar no CI via secrets
- Versionar porque nao contem credenciais

**Decisao:** Versionar — o arquivo usa apenas `env_var()` e o target `ci`
usa `:memory:`. Nenhuma credencial real esta presente.

**Consequencia:** CI funciona sem gerar o arquivo dinamicamente. README
explica a decisao e documenta que em projetos com credenciais reais
o arquivo ficaria no `.gitignore` e seria gerado via GitHub Secrets
ou HashiCorp Vault.

**Em producao:** O profiles.yml nao seria versionado. O CI geraria o
arquivo usando secrets do repositorio. Empresas grandes usam gerenciadores
dedicados (Vault, AWS Secrets Manager, Azure Key Vault).

---

## ADR-008: Templater jinja no CI, templater dbt no pre-commit

**Contexto:** sqlfluff precisa de um templater para processar Jinja nos
arquivos SQL antes de analisar.

**Alternativas:**
- Templater `dbt` em todos os contextos (requer banco, profiles, pacotes)
- Templater `jinja` no CI (basico, sem dependencias externas)

**Decisao:** CI usa `jinja`, pre-commit local usa `dbt`.

**Racional:** O templater `dbt` compila o projeto inteiro — precisa de
banco, profiles e pacotes instalados. No CI isso adiciona complexidade
desnecessaria. O templater `jinja` substitui `{{ ref('x') }}` por
placeholders e e suficiente para regras de estilo (indentacao, espacamento,
qualificacao de colunas). O pre-commit local ja tem o ambiente configurado,
entao usa `dbt` para analise completa.

**Consequencia:** CI e rapido e simples. Pre-commit local e mais rigoroso.

---

## ADR-009: DBT_TARGET ci para compilacao no CI

**Contexto:** O target `dev` aponta para um arquivo DuckDB fisico que
nao existe no CI.

**Alternativas:**
- Criar um DuckDB vazio no CI (workaround)
- Usar target `ci` com `:memory:` (solucao limpa)

**Decisao:** `DBT_TARGET=ci` com `path: ":memory:"` — nao precisa de
arquivo fisico para compilar, buildar ou testar no CI.

**Consequencia:** `profiles.yml` tem tres targets: `dev` (local), `ci`
(memoria), `prod` (produtivo com env_vars). O CI usa `ci` via variavel
de ambiente `DBT_TARGET`.

---

## ADR-010: Airflow com venv isolado para dbt (Padrao 1)

**Contexto:** Airflow e dbt tem dependencias Python conflitantes. Instalar
ambos no mesmo ambiente causa `ResolutionTooDeep` no pip.

**Alternativas avaliadas:**

| Padrao | Descricao | Tempo | Complexidade |
|---|---|---|---|
| 1. Venv isolado | dbt num venv separado dentro do container Airflow | ~1h | Baixa |
| 2. Containers separados | dbt em container proprio, Airflow orquestra via DockerOperator | ~3h | Media |
| 3. Servicos gerenciados | Airflow + dbt Cloud como servicos independentes | N/A | Alta |

**Decisao:** Padrao 1 — recomendado pela documentacao oficial do
Astronomer Cosmos. O Dockerfile cria `/home/airflow/dbt-env` com dbt-core
e dbt-duckdb. O ambiente Airflow instala apenas Cosmos e providers.

**Racional contra Padrao 2:** DuckDB e single-process (um writer por vez).
Compartilhar o arquivo entre containers via volume Docker no Windows e
fonte de problemas de lock e performance. Alem disso, o Padrao 2 perde
a task-level observability do Cosmos (cada modelo dbt como task Airflow).

**Consequencia:**
- `requirements-airflow.txt` tem apenas Cosmos e providers
- Dockerfile cria venv isolado com dbt + dependencias de ingestao
- `financial_pipeline.py` usa `subprocess` para chamar scripts de ingestao
  com o Python do venv isolado
- README documenta que para multiplos projetos dbt a evolucao natural
  seria containers separados (Padrao 2)

---

## ADR-011: Cosmos com profiles_yml_filepath em vez de ProfileMapping

**Contexto:** O Cosmos precisa de um ProfileConfig para conectar ao DuckDB.

**Alternativas:**
- `DuckDBUserPasswordProfileMapping` (classe de mapeamento do Cosmos)
- `profiles_yml_filepath` (aponta para o profiles.yml existente)

**Decisao:** `profiles_yml_filepath` — a classe
`DuckDBUserPasswordProfileMapping` nao existe no Cosmos 1.8.0. O mais
robusto e apontar para o `profiles.yml` que ja existe no projeto.

**Consequencia:** Zero dependencia de classes internas do Cosmos que
podem mudar entre versoes. O profiles.yml e a unica fonte de verdade.

---

## ADR-012: Docker Compose .env para interpolacao e env_file

**Contexto:** Docker Compose usa dois mecanismos distintos para variaveis:
- `${VAR}` no YAML → resolvido do `.env` ou shell (parse time)
- `env_file:` → injetado no container (runtime)

**Alternativas:**
- Dois arquivos separados (`.env` + `.env.airflow`)
- Um unico arquivo `.env` para ambos os propositos

**Decisao:** Um unico `.env` dentro de `orchestration/` — serve tanto
para interpolacao do compose quanto para injecao no container.

**Consequencia:** Fluxo simples: `.env.airflow.example` → `.env`.
Sem duplicacao de variaveis entre arquivos.

---

## ADR-013: Permissoes do volume Docker para DuckDB

**Contexto:** Volumes nomeados do Docker sao criados com permissoes root.
O container Airflow roda como usuario `airflow` (nao-root).

**Decisao:** Adicionar `RUN mkdir -p /opt/airflow/data` no Dockerfile.
Quando o Docker monta o volume sobre esse caminho, herda as permissoes
do diretorio criado pelo usuario `airflow`.

**Consequencia:** O DuckDB pode ser criado e escrito sem erros de permissao.

---

## ADR-014: MSYS_NO_PATHCONV para comandos Docker no Git Bash

**Contexto:** Git Bash no Windows converte automaticamente caminhos Linux
para Windows (`/home/airflow/` → `C:/Program Files/Git/home/airflow/`).
Isso quebra comandos `docker compose exec` com paths do container.

**Decisao:** Prefixar com `MSYS_NO_PATHCONV=1` todos os comandos
`docker compose exec` que usam paths Linux.

**Consequencia:** Todos os comandos Docker no Git Bash precisam desse
prefixo. O `orchestration/README.md` documenta isso.

---

## ADR-015: noqa RF02 no modelo incremental

**Contexto:** O sqlfluff regra RF02 exige que todas as colunas sejam
qualificadas com alias de tabela. Dentro do bloco `{% if is_incremental() %}`
o Jinja gera um contexto que o linter nao reconhece, gerando falso positivo.

**Decisao:** `-- noqa: RF02` na linha especifica do bloco incremental.

**Consequencia:** A regra continua ativa para o restante do projeto.
Apenas a linha do falso positivo e suprimida, com comentario explicando
o motivo.

---

## ADR-016: GitHub Pages para dbt Docs

**Contexto:** A documentacao dbt precisa ser acessivel sem rodar
`dbt docs serve` localmente.

**Decisao:** Workflow `docs.yml` gera os docs e publica no GitHub Pages
automaticamente a cada push em `main`.

**Prerequisito manual:** Ativar GitHub Pages em
`Settings → Pages → Source: GitHub Actions` (unica acao manual necessaria
por quem fizer fork).

---

## ADR-017: BACEN_END_DATE dinamico

**Contexto:** O `.env` tinha `BACEN_END_DATE=2025-12-31` hardcoded,
limitando a ingestao ao passado.

**Decisao:** Remover do `.env`. O script `ingest_bacen.py` usa
`date.today()` como fallback quando a variavel nao esta definida.

**Consequencia:** Cada execucao busca dados ate a data atual automaticamente.

---

## Decisoes para evolucao futura

**Se o projeto crescer para multiplos projetos dbt:**
Migrar de Padrao 1 (venv isolado) para Padrao 2 (containers separados).
Cada projeto dbt teria sua propria imagem Docker, orquestrada pelo
Airflow via `DockerOperator` ou `KubernetesPodOperator`.

**Se o DuckDB se tornar limitante:**
Migrar para PostgreSQL ou Snowflake. O profiles.yml ja tem a estrutura
de targets (`dev`, `ci`, `prod`). A migracao envolve: mudar o adapter,
atualizar a estrategia incremental (de `delete+insert` para `merge`),
e ajustar as queries especificas de DuckDB.

**Se o projeto precisar de secrets reais:**
Migrar de profiles.yml versionado para gerado no CI via GitHub Secrets.
Em producao enterprise, usar HashiCorp Vault ou equivalente.

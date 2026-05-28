"""
Ingestão de séries temporais via API SGS/Banco Central do Brasil.

API pública, sem autenticação. Documentação:
https://www.bcb.gov.br/htms/sgs/help.pdf

Séries ingeridas:
  11   -> Selic diária (% a.a.)
  433  -> IPCA mensal (variação %)
  1    -> USD/BRL diário (venda)
  189  -> IGP-M mensal (variação %)
  4189 -> CDI diário (% a.a.)
  7811 -> Juro real ex-ante mensal (% a.a.)
"""

import os
import logging
import duckdb
import requests
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DUCKDB_PATH   = os.getenv("DUCKDB_PATH", "./data/financial_dw.duckdb")
START_DATE    = os.getenv("BACEN_START_DATE", "2020-01-01")
END_DATE      = os.getenv("BACEN_END_DATE", date.today().strftime("%Y-%m-%d"))
BACEN_SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"

SERIES_MAP = {
    11:   {"name": "selic_rate",         "frequency": "daily",   "unit": "pct_per_year"},
    433:  {"name": "ipca_inflation",     "frequency": "monthly", "unit": "pct_change"},
    1:    {"name": "usd_brl_rate",       "frequency": "daily",   "unit": "brl_per_usd"},
    189:  {"name": "igpm_inflation",     "frequency": "monthly", "unit": "pct_change"},
    4189: {"name": "cdi_rate",           "frequency": "daily",   "unit": "pct_per_year"},
    7811: {"name": "real_interest_rate", "frequency": "monthly", "unit": "pct_per_year"},
}


def fetch_series(series_code: int, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Consome a API SGS e retorna DataFrame normalizado.
    A API exige datas no formato DD/MM/YYYY — convertemos aqui.
    """
    start_fmt = datetime.strptime(start_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    end_fmt   = datetime.strptime(end_date,   "%Y-%m-%d").strftime("%d/%m/%Y")
    url       = BACEN_SGS_URL.format(code=series_code)
    params    = {"formato": "json", "dataInicial": start_fmt, "dataFinal": end_fmt}

    logger.info(f"Fetching series {series_code} ({SERIES_MAP[series_code]['name']})")
    response  = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    raw = response.json()
    if not raw:
        logger.warning(f"Series {series_code}: no data returned")
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    df["date"]  = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.date
    df["value"] = pd.to_numeric(df["valor"].str.replace(",", "."), errors="coerce")

    meta = SERIES_MAP[series_code]
    df["series_code"] = series_code
    df["series_name"] = meta["name"]
    df["frequency"]   = meta["frequency"]
    df["unit"]        = meta["unit"]
    df["ingested_at"] = datetime.utcnow()

    return df[["series_code", "series_name", "frequency", "unit", "date", "value", "ingested_at"]]


def load_to_duckdb(df: pd.DataFrame, conn: duckdb.DuckDBPyConnection) -> None:
    """
    Upsert idempotente com INSERT OR REPLACE.
    Chave primária composta: (series_code, date).
    Re-rodar a ingestão nunca duplica registros.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw.bacen_series (
            series_code  INTEGER   NOT NULL,
            series_name  VARCHAR   NOT NULL,
            frequency    VARCHAR   NOT NULL,
            unit         VARCHAR   NOT NULL,
            date         DATE      NOT NULL,
            value        DOUBLE,
            ingested_at  TIMESTAMP NOT NULL,
            PRIMARY KEY (series_code, date)
        )
    """)
    conn.execute("INSERT OR REPLACE INTO raw.bacen_series SELECT * FROM df WHERE value IS NOT NULL")
    rows = conn.execute("SELECT COUNT(*) FROM raw.bacen_series").fetchone()[0]
    logger.info(f"raw.bacen_series: {rows} total rows after upsert")


def main():
    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    with duckdb.connect(DUCKDB_PATH) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        all_series = []
        for code in SERIES_MAP:
            try:
                df = fetch_series(code, START_DATE, END_DATE)
                if not df.empty:
                    all_series.append(df)
            except Exception as e:
                logger.error(f"Error series {code}: {e}", exc_info=True)

        if all_series:
            combined = pd.concat(all_series, ignore_index=True)
            load_to_duckdb(combined, conn)
            logger.info(f"BACEN ingestion done: {len(combined)} records, "
                        f"{combined['series_code'].nunique()} series")


if __name__ == "__main__":
    main()

"""
Ingestao de cotacoes historicas B3 via Brapi (brapi.dev).
Tickers brasileiros sem sufixo .SA (ex: PETR4, nao PETR4.SA).
Token opcional para tickers alem dos 4 gratuitos (PETR4, MGLU3, VALE3, ITUB4).
Obtenha seu token em: https://brapi.dev/dashboard
"""

import os
import time
import logging
import requests
import duckdb
import pandas as pd
from datetime import datetime, date, timezone
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/financial_dw.duckdb")
START_DATE  = os.getenv("BACEN_START_DATE", "2020-01-01")
BRAPI_TOKEN = os.getenv("BRAPI_API_KEY")
TICKERS     = [t.strip() for t in os.getenv("TICKERS", "PETR4,MGLU3,VALE3,ITUB4").split(",")]

# Brapi usa range relativo (ex: '5y'), nao datas absolutas.
# Usamos 'max' e filtramos por START_DATE no script.
BRAPI_RANGE = "max"

TICKER_META = {
    "PETR4": {"company": "Petrobras",      "sector": "Energy",      "index": "IBOVESPA"},
    "VALE3": {"company": "Vale",            "sector": "Materials",   "index": "IBOVESPA"},
    "ITUB4": {"company": "Itau Unibanco",   "sector": "Financials",  "index": "IBOVESPA"},
    "BBDC4": {"company": "Bradesco",        "sector": "Financials",  "index": "IBOVESPA"},
    "WEGE3": {"company": "WEG",             "sector": "Industrials", "index": "IBOVESPA"},
    "MGLU3": {"company": "Magazine Luiza",  "sector": "Consumer",    "index": "IBOVESPA"},
}

BRAPI_BASE_URL = "https://brapi.dev/api/quote"
DELAY_BETWEEN_TICKERS = 2  # segundos — Brapi e bem mais tolerante que Yahoo Finance


def fetch_ticker(ticker: str) -> pd.DataFrame:
    """
    Busca historico OHLCV de um ticker via Brapi.
    date vem como timestamp Unix e e convertido para date.
    dividends e stock_splits nao sao fornecidos pela Brapi — preenchidos com 0.
    """
    logger.info(f"Fetching {ticker}")

    headers = {}
    if BRAPI_TOKEN:
        headers["Authorization"] = f"Bearer {BRAPI_TOKEN}"

    try:
        response = requests.get(
            f"{BRAPI_BASE_URL}/{ticker}",
            params={"range": BRAPI_RANGE, "interval": "1d"},
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"{ticker}: request failed — {e}")
        return pd.DataFrame()

    result = response.json().get("results", [{}])[0]
    historical = result.get("historicalDataPrice", [])

    if not historical:
        logger.warning(f"{ticker}: no historical data returned")
        return pd.DataFrame()

    df = pd.DataFrame(historical)

    # Converte timestamp Unix para date e filtra pelo START_DATE
    df["date"] = pd.to_datetime(df["date"], unit="s").dt.date
    df = df[df["date"] >= datetime.strptime(START_DATE, "%Y-%m-%d").date()]

    # Renomeia adjustedClose para adj_close
    df = df.rename(columns={"adjustedClose": "adj_close"})

    # Brapi nao fornece dividendos nem splits — preenchemos com 0 para manter schema
    df["dividends"]    = 0.0
    df["stock_splits"] = 0.0

    meta = TICKER_META.get(ticker, {"company": ticker, "sector": "Unknown", "index": "Unknown"})
    df["ticker"]       = ticker
    df["company"]      = meta["company"]
    df["sector"]       = meta["sector"]
    df["market_index"] = meta["index"]
    df["ingested_at"]  = datetime.now(timezone.utc)

    cols = ["ticker", "company", "sector", "market_index", "date",
            "open", "high", "low", "close", "adj_close",
            "volume", "dividends", "stock_splits", "ingested_at"]
    return df[[c for c in cols if c in df.columns]]


def load_to_duckdb(df: pd.DataFrame, conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw.market_prices (
            ticker        VARCHAR   NOT NULL,
            company       VARCHAR,
            sector        VARCHAR,
            market_index  VARCHAR,
            date          DATE      NOT NULL,
            open          DOUBLE,
            high          DOUBLE,
            low           DOUBLE,
            close         DOUBLE,
            adj_close     DOUBLE,
            volume        BIGINT,
            dividends     DOUBLE,
            stock_splits  DOUBLE,
            ingested_at   TIMESTAMP NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("INSERT OR REPLACE INTO raw.market_prices SELECT * FROM df")
    rows = conn.execute("SELECT COUNT(*) FROM raw.market_prices").fetchone()[0]
    logger.info(f"raw.market_prices: {rows} rows after upsert")


def main():
    if not BRAPI_TOKEN:
        logger.warning(
            "BRAPI_API_KEY nao definido — apenas PETR4, MGLU3, VALE3 e ITUB4 funcionam sem token"
        )

    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    with duckdb.connect(DUCKDB_PATH) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        all_data = []
        for ticker in TICKERS:
            try:
                df = fetch_ticker(ticker)
                if not df.empty:
                    all_data.append(df)
                    logger.info(f"{ticker}: {len(df)} rows fetched")
            except Exception as e:
                logger.error(f"Error {ticker}: {e}", exc_info=True)
            time.sleep(DELAY_BETWEEN_TICKERS)

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            load_to_duckdb(combined, conn)
            logger.info(
                f"Market ingestion done: {len(combined)} records, "
                f"{combined['ticker'].nunique()} tickers"
            )
        else:
            logger.warning("No data ingested — all tickers failed or returned empty")


if __name__ == "__main__":
    main()

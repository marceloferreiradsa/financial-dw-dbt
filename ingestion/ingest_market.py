"""
Ingestao de cotacoes historicas B3 via yfinance (Yahoo Finance).
Tickers brasileiros tem sufixo .SA (ex: PETR4.SA).
"""

import os
import time
import logging
import duckdb
import yfinance as yf
import pandas as pd
from datetime import datetime, date, timezone
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/financial_dw.duckdb")
START_DATE  = os.getenv("BACEN_START_DATE", "2020-01-01")
END_DATE    = os.getenv("BACEN_END_DATE", date.today().strftime("%Y-%m-%d"))
TICKERS     = [t.strip() for t in os.getenv("TICKERS", "PETR4.SA,VALE3.SA,ITUB4.SA,BBDC4.SA,WEGE3.SA,MGLU3.SA").split(",")]

TICKER_META = {
    "PETR4.SA": {"company": "Petrobras",      "sector": "Energy",      "index": "IBOVESPA"},
    "VALE3.SA": {"company": "Vale",            "sector": "Materials",   "index": "IBOVESPA"},
    "ITUB4.SA": {"company": "Itau Unibanco",   "sector": "Financials",  "index": "IBOVESPA"},
    "BBDC4.SA": {"company": "Bradesco",        "sector": "Financials",  "index": "IBOVESPA"},
    "WEGE3.SA": {"company": "WEG",             "sector": "Industrials", "index": "IBOVESPA"},
    "MGLU3.SA": {"company": "Magazine Luiza",  "sector": "Consumer",    "index": "IBOVESPA"},
}

# Delay entre tickers e tentativas para respeitar rate limit do Yahoo Finance
DELAY_BETWEEN_TICKERS = 5   # segundos entre cada ticker
DELAY_ON_RETRY        = 15  # segundos de espera antes de retry


def fetch_ticker(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Baixa OHLCV + dividendos + splits.
    auto_adjust=False mantem precos nominais + adj_close separado,
    permitindo analises que precisam distinguir os dois.
    Inclui retry automatico em caso de rate limit.
    """
    logger.info(f"Fetching {ticker}")
    data = yf.download(ticker, start=start, end=end,
                       auto_adjust=False, actions=True,
                       progress=False, threads=False)

    if data.empty:
        logger.warning(f"{ticker}: no data, retrying in {DELAY_ON_RETRY}s...")
        time.sleep(DELAY_ON_RETRY)
        data = yf.download(ticker, start=start, end=end,
                           auto_adjust=False, actions=True,
                           progress=False, threads=False)

    if data.empty:
        logger.warning(f"{ticker}: no data after retry, skipping")
        return pd.DataFrame()

    # reset_index primeiro para trazer 'Date' como coluna,
    # depois lowercase em todas as colunas de uma vez so
    data = data.reset_index()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0].lower().replace(" ", "_") for col in data.columns]
    else:
        data.columns = [c.lower().replace(" ", "_") for c in data.columns]

    data["date"] = pd.to_datetime(data["date"]).dt.date

    meta = TICKER_META.get(ticker, {"company": ticker, "sector": "Unknown", "index": "Unknown"})
    data["ticker"]       = ticker
    data["company"]      = meta["company"]
    data["sector"]       = meta["sector"]
    data["market_index"] = meta["index"]
    data["ingested_at"]  = datetime.now(timezone.utc)

    cols = ["ticker", "company", "sector", "market_index", "date",
            "open", "high", "low", "close", "adj_close",
            "volume", "dividends", "stock_splits", "ingested_at"]
    return data[[c for c in cols if c in data.columns]]


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
    os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)
    with duckdb.connect(DUCKDB_PATH) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        all_data = []
        for ticker in TICKERS:
            try:
                df = fetch_ticker(ticker, START_DATE, END_DATE)
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                logger.error(f"Error {ticker}: {e}", exc_info=True)
            time.sleep(DELAY_BETWEEN_TICKERS)

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            load_to_duckdb(combined, conn)
            logger.info(f"Market ingestion done: {len(combined)} records, "
                        f"{combined['ticker'].nunique()} tickers")
        else:
            logger.warning("No data ingested — all tickers failed or returned empty")


if __name__ == "__main__":
    main()

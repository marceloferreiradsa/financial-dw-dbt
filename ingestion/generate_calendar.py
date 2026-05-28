"""
Gera seeds/dim_calendar.csv com todas as datas de 2019 a 2030.
Execute uma vez após o setup: python ingestion/generate_calendar.py
"""

import pandas as pd
from pathlib import Path

HOLIDAYS_BR = {
    "01-01", "04-21", "05-01", "09-07", "10-12", "11-02", "11-15", "12-25",
    "2020-02-24", "2020-02-25", "2020-04-10", "2020-06-11",
    "2021-02-15", "2021-02-16", "2021-04-02", "2021-06-03",
    "2022-02-28", "2022-03-01", "2022-04-15", "2022-06-16",
    "2023-02-20", "2023-02-21", "2023-04-07", "2023-06-08",
    "2024-02-12", "2024-02-13", "2024-03-29", "2024-05-30",
    "2025-03-03", "2025-03-04", "2025-04-18", "2025-06-19",
    "2026-02-16", "2026-02-17", "2026-04-03", "2026-06-04",
}

def is_holiday(d: pd.Timestamp) -> bool:
    return d.strftime("%m-%d") in HOLIDAYS_BR or d.strftime("%Y-%m-%d") in HOLIDAYS_BR

dates = pd.date_range("2019-01-01", "2030-12-31", freq="D")
rows = []
for d in dates:
    is_weekend = d.weekday() >= 5
    holiday    = is_holiday(d)
    rows.append({
        "date_id":        int(d.strftime("%Y%m%d")),
        "full_date":      d.strftime("%Y-%m-%d"),
        "year":           d.year,
        "quarter":        d.quarter,
        "month":          d.month,
        "month_name":     d.strftime("%B"),
        "week":           d.isocalendar().week,
        "day_of_week":    d.weekday() + 1,
        "day_name":       d.strftime("%A"),
        "is_weekend":     is_weekend,
        "is_business_day": not is_weekend and not holiday,
    })

df  = pd.DataFrame(rows)
out = Path(__file__).parent.parent / "dbt_project" / "seeds" / "dim_calendar.csv"
df.to_csv(out, index=False)
print(f"dim_calendar.csv gerado: {len(df)} linhas -> {out}")

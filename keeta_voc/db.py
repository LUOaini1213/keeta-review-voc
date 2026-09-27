"""SQLite layer: load reviews + labels, run the committed queries in sql/."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .taxonomy import label_names

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
QUERIES = {
    "overview": "01_overview.sql",
    "issue_share_by_storefront": "02_issue_share_by_storefront.sql",
    "issue_share_by_rating": "03_issue_share_by_rating.sql",
    "pain_points": "04_pain_points.sql",
    "by_version": "05_by_version.sql",
    "month_trend": "06_month_trend.sql",
    "language_mix": "07_language_mix.sql",
    "cooccurrence": "08_cooccurrence.sql",
    "region_band": "09_region_band.sql",
}
REVIEW_COLS = ["review_key", "storefront", "region", "rating", "app_version", "review_date", "month", "lang", "n_chars"]


def region_of(storefront: str) -> str:
    return "hk" if storefront == "hk" else "gulf"


def connect(reviews: pd.DataFrame, labels: dict[str, dict[str, list[str] | None]]) -> sqlite3.Connection:
    """reviews: DataFrame with REVIEW_COLS; labels: {method: {review_key: [labels] or None}}."""
    con = sqlite3.connect(":memory:")
    con.executescript((SQL_DIR / "00_schema.sql").read_text(encoding="utf-8"))
    con.executemany("INSERT INTO taxonomy VALUES (?, ?)", [(n, i) for i, n in enumerate(label_names())])
    reviews = reviews.assign(region=reviews["storefront"].map(region_of))
    rows = reviews[REVIEW_COLS].astype({"rating": int, "n_chars": int}).itertuples(index=False, name=None)
    con.executemany(f"INSERT INTO reviews VALUES ({','.join('?' * len(REVIEW_COLS))})", list(rows))
    known = set(reviews["review_key"])
    for method, lab in labels.items():
        con.executemany("INSERT INTO labels VALUES (?, ?, ?)",
                        [(k, method, x) for k, xs in lab.items() if xs and k in known for x in xs])
    con.commit()
    return con


def run(con: sqlite3.Connection, name: str, **params) -> pd.DataFrame:
    sql = (SQL_DIR / QUERIES[name]).read_text(encoding="utf-8")
    return pd.read_sql_query(sql, con, params=params)

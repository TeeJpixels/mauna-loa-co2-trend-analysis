"""Reproducible analysis of the historical Mauna Loa weekly CO2 series."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw" / "mauna_loa_weekly_co2.csv"
OUT = ROOT / "outputs"
DB = OUT / "mauna_loa_co2.sqlite"


def load_and_clean() -> pd.DataFrame:
    if not RAW.exists():
        raise FileNotFoundError(f"Missing dataset: {RAW}")
    raw = pd.read_csv(RAW)
    required = {"date", "co2"}
    if not required.issubset(raw.columns):
        raise ValueError(f"Expected columns {sorted(required)}; found {raw.columns.tolist()}")
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
    df["co2"] = pd.to_numeric(df["co2"], errors="coerce")
    df = df.dropna(subset=["date", "co2"])
    df = df[df["co2"].between(250, 450)]
    df = df.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def run_sql(df: pd.DataFrame, monthly: pd.DataFrame, annual: pd.DataFrame) -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    try:
        df.to_sql("weekly_co2", con, index=False, if_exists="replace")
        monthly.to_sql("monthly_co2", con, index=False, if_exists="replace")
        queries = {
            "annual_summary": """
                SELECT year, ROUND(AVG(co2), 2) AS mean_co2_ppm,
                       ROUND(MIN(co2), 2) AS min_weekly_co2_ppm,
                       ROUND(MAX(co2), 2) AS max_weekly_co2_ppm,
                       COUNT(*) AS weekly_observations
                FROM weekly_co2 GROUP BY year ORDER BY year;
            """,
            "monthly_seasonality": """
                SELECT month, ROUND(AVG(co2), 2) AS mean_co2_ppm,
                       COUNT(*) AS observations
                FROM weekly_co2 GROUP BY month ORDER BY month;
            """,
            "first_and_last": """
                SELECT 'first' AS record, date, co2
                FROM weekly_co2 WHERE date = (SELECT MIN(date) FROM weekly_co2)
                UNION ALL
                SELECT 'last' AS record, date, co2
                FROM weekly_co2 WHERE date = (SELECT MAX(date) FROM weekly_co2);
            """
        }
        return {name: pd.read_sql_query(sql, con) for name, sql in queries.items()}
    finally:
        con.close()


def make_charts(df: pd.DataFrame, monthly: pd.DataFrame, annual: pd.DataFrame, seasonality: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 5.5))
    plt.plot(df["date"], df["co2"], linewidth=0.75, alpha=0.55, label="Weekly observations")
    rolling = df.set_index("date")["co2"].rolling("365D", min_periods=20).mean()
    plt.plot(rolling.index, rolling.values, linewidth=2.0, label="365-day rolling mean")
    plt.title("Mauna Loa Atmospheric CO2 (1958-2001)")
    plt.xlabel("Date")
    plt.ylabel("CO2 concentration (ppm)")
    plt.legend()
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(OUT / "weekly_co2_trend.png", dpi=180)
    plt.close()

    plt.figure(figsize=(10, 5.5))
    plt.plot(annual["year"], annual["mean_co2_ppm"], marker="o", markersize=2.8, linewidth=1.6)
    plt.title("Annual Mean Atmospheric CO2")
    plt.xlabel("Year")
    plt.ylabel("Annual mean CO2 (ppm)")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUT / "annual_co2_mean.png", dpi=180)
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.plot(seasonality["month"], seasonality["mean_co2_ppm"], marker="o", linewidth=1.8)
    ax.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_ylim(seasonality["mean_co2_ppm"].min() - 1, seasonality["mean_co2_ppm"].max() + 1)
    ax.set_title("Average CO2 by Calendar Month (Historical Seasonal Pattern)")
    ax.set_xlabel("Calendar month")
    ax.set_ylabel("Mean CO2 (ppm)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "monthly_seasonality.png", dpi=180)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_and_clean()
    indexed = df.set_index("date").sort_index()
    monthly_series = indexed["co2"].resample("MS").mean()
    monthly = monthly_series.rename("mean_co2_ppm").reset_index()
    monthly["year"] = monthly["date"].dt.year
    monthly["month"] = monthly["date"].dt.month
    annual = df.groupby("year", as_index=False).agg(
        mean_co2_ppm=("co2", "mean"),
        min_weekly_co2_ppm=("co2", "min"),
        max_weekly_co2_ppm=("co2", "max"),
        weekly_observations=("co2", "count")
    )
    seasonality = df.groupby("month", as_index=False).agg(
        mean_co2_ppm=("co2", "mean"),
        observations=("co2", "count")
    )
    sql = run_sql(df, monthly, annual)

    df.to_csv(OUT / "clean_weekly_co2.csv", index=False)
    monthly.to_csv(OUT / "monthly_co2.csv", index=False)
    annual.to_csv(OUT / "annual_co2_summary.csv", index=False)
    seasonality.to_csv(OUT / "monthly_seasonality.csv", index=False)
    sql["annual_summary"].to_csv(OUT / "annual_summary_sql.csv", index=False)
    sql["monthly_seasonality"].to_csv(OUT / "monthly_seasonality_sql.csv", index=False)
    sql["first_and_last"].to_csv(OUT / "first_and_last_observation.csv", index=False)

    make_charts(df, monthly, annual, seasonality)
    first = df.iloc[0]
    last = df.iloc[-1]
    slope = np.polyfit((df["date"] - df["date"].min()).dt.days / 365.2425, df["co2"], 1)[0]
    spread = last["co2"] - first["co2"]
    summary = (
        f"Valid weekly observations: {len(df):,}\n"
        f"Period: {first['date'].date()} to {last['date'].date()}\n"
        f"First recorded value in included sample: {first['co2']:.1f} ppm\n"
        f"Last recorded value in included sample: {last['co2']:.1f} ppm\n"
        f"Difference between end and start observations: {spread:.1f} ppm\n"
        f"Simple linear trend across this historical sample: {slope:.2f} ppm per year\n"
        "Note: the included legacy dataset ends in December 2001; this is not a current CO2 reading.\n"
    )
    (OUT / "executive_summary.txt").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Outputs written to: {OUT}")


if __name__ == "__main__":
    main()

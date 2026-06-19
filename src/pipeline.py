"""
pipeline.py

The main entry point. Running "python src/pipeline.py" does the full job:
fetch every tracked metric from FRED, clean it, and write it into Postgres
using safe UPSERT logic so re-running the script never creates duplicates.

This file deliberately keeps extraction (fred_client.py) and configuration
(config.py) separate, but folds validation, transformation, and loading
together. For five metrics and one data source, splitting those three steps
into three more files would add import overhead without adding clarity.
If this pipeline ever grows to ten or more data sources with different
shapes, that is the point where splitting them back out would be worth it.
"""

import logging
import sys

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from config import DATABASE_URL, METRICS
from fred_client import fetch_series

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
    stream=sys.stdout,  # GitHub Actions captures stdout as the run log automatically.
)
logger = logging.getLogger("pipeline")


def clean_records(raw_observations: list[dict], metric_id: str) -> pd.DataFrame:
    """
    Takes the raw list of {"date": ..., "value": ...} dictionaries straight
    from FRED and returns a clean DataFrame ready for the database.

    This is the validation and transformation step. It is intentionally
    explicit and easy to read rather than hidden inside a generic schema
    library, because FRED's data quality issue is always the same one:
    missing observations are represented as the literal string ".".
    """
    if not raw_observations:
        logger.warning("No observations returned for %s, skipping.", metric_id)
        return pd.DataFrame(columns=["metric_id", "observation_date", "metric_value"])

    df = pd.DataFrame(raw_observations)[["date", "value"]]
    df.columns = ["observation_date", "metric_value"]

    # FRED's missing-value marker is "." Convert it to a real NaN
    # so pandas can handle it, instead of treating it as a string later on.
    df["metric_value"] = pd.to_numeric(df["metric_value"], errors="coerce")
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce").dt.date

    before = len(df)
    df = df.dropna(subset=["metric_value", "observation_date"])
    dropped = before - len(df)
    if dropped:
        logger.warning(
            "Dropped %d invalid or missing rows for %s.", dropped, metric_id
        )

    df["metric_id"] = metric_id
    return df[["metric_id", "observation_date", "metric_value"]]


def upsert_records(conn, df: pd.DataFrame) -> int:
    """
    Writes a DataFrame into fact_macro_risk_indicators using
    ON CONFLICT DO UPDATE, so running this script five times with the
    same data results in the same five rows, not five duplicates.

    Returns the number of rows written, used for the run summary log line.
    """
    if df.empty:
        return 0

    records = list(df.itertuples(index=False, name=None))

    query = """
        INSERT INTO fact_macro_risk_indicators
            (metric_id, observation_date, metric_value)
        VALUES %s
        ON CONFLICT (metric_id, observation_date)
        DO UPDATE SET
            metric_value = EXCLUDED.metric_value,
            extracted_at_utc = TIMEZONE('utc', NOW());
    """

    with conn.cursor() as cur:
        execute_values(cur, query, records)
    conn.commit()
    return len(records)


def main() -> None:
    logger.info("Pipeline run starting for %d tracked metrics.", len(METRICS))

    conn = psycopg2.connect(DATABASE_URL)
    total_written = 0
    failures = []

    try:
        for metric_id in METRICS:
            try:
                raw = fetch_series(metric_id)
                clean_df = clean_records(raw, metric_id)
                written = upsert_records(conn, clean_df)
                total_written += written
                logger.info("%s: %d rows written.", metric_id, written)
            except Exception as exc:  # noqa: BLE001
                # One bad metric should not take down the whole run.
                logger.error("%s failed: %s", metric_id, exc)
                failures.append(metric_id)
    finally:
        conn.close()

    logger.info(
        "Pipeline run finished. %d total rows written. Failures: %s",
        total_written, failures or "none",
    )

    if failures:
        # Non-zero exit code makes the GitHub Actions run show as failed,
        # which is what triggers the red X / email notification.
        sys.exit(1)


if __name__ == "__main__":
    main()
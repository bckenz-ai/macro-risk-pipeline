# Macro & Credit Risk ETL Pipeline

An automated, scheduled data pipeline that pulls macroeconomic and consumer
credit risk indicators from the Federal Reserve Economic Data (FRED) API,
validates and cleans the data, and loads it into a cloud Postgres database
on a daily schedule with zero manual intervention.

**Live dashboard:** https://public.tableau.com/views/macro-risk-dashboard/Dashboard1?:language=en-GB&publish=yes&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link
**Daily run history:** see the Actions tab of this repository

## What this project tracks

| Metric | FRED ID | Frequency | Why it matters |
|---|---|---|---|
| 3-Month SOFR | SOFR90DAYAVG | Daily | Benchmark wholesale funding rate, a leading indicator for shifting interest rate conditions |
| Consumer Price Index | CPIAUCSL | Monthly | Tracks inflation pressure on consumer purchasing power |
| Real GDP | GDPC1 | Quarterly | Tracks broader economic growth or recession risk |
| Credit Card Delinquency Rate | DRCCLACBS | Quarterly | Leading indicator for retail credit risk |
| Bank Prime Loan Rate | MPRIME | Daily | Base rate banks charge their most creditworthy clients |

## Why this exists

Most student portfolios are full of one-off notebooks where a CSV was
downloaded once and analyzed manually. This project is built to run on its
own. It fetches new data every day, handles network failures without
crashing, and never writes duplicate records even if it runs twice in a
row. That is the difference between a script and a pipeline.

## Architecture

```
FRED API
   |
   v
GitHub Actions (daily cron trigger)
   |
   v
Python: extract -> clean -> validate -> upsert
   |
   v
Postgres (Supabase / Neon, free tier)
   |
   v
SQL views (vw_systemic_financial_strain, vw_systemic_strain_zscore)
   |
   v
Tableau Public dashboard
```

No servers to maintain. No cloud bill to monitor. The entire orchestration
layer is GitHub Actions, and the entire storage layer is a managed
serverless Postgres instance on its free tier.

## Tech stack

- **Python 3.11**: requests, pandas, psycopg2-binary
- **PostgreSQL**: hosted on Supabase or Neon (serverless, free tier)
- **GitHub Actions**: scheduling and execution, no servers to manage
- **Tableau Public**: dashboard layer
- **pytest**: unit tests for the cleaning logic and the retry logic

## Project structure

```
macro-risk-pipeline/
├── .github/workflows/run_etl.yml    # Daily scheduled trigger
├── src/
│   ├── config.py                    # Tracked metrics and environment variables
│   ├── fred_client.py               # FRED API calls with retry and backoff
│   └── pipeline.py                  # Clean, validate, and load (UPSERT) into Postgres
├── sql/schema.sql                   # Table definition, indexes, and analytical views
├── tests/test_pipeline.py           # pytest suite
├── requirements.txt
├── .env.example
└── README.md
```

## Running it locally

```
git clone https://github.com/bckenz-ai/macro-risk-pipeline.git
cd macro-risk-pipeline
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env` with a free FRED API key and your Postgres connection string,
then run the schema once against your database (Supabase SQL Editor or
Neon's SQL console both work), and run:

```
python src/pipeline.py
```

## Data integrity notes

FRED represents missing observations with the literal string `.` instead of
leaving the field blank. The cleaning step in `pipeline.py` explicitly
checks for this and drops those rows rather than letting them silently
become zero, which would corrupt the historical average.

The pipeline uses `ON CONFLICT (metric_id, observation_date) DO UPDATE`
when writing to Postgres, so running it any number of times for the same
day always results in one row per metric per date, never duplicates.

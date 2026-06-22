-- Core fact table. One row per metric per date.
-- The composite primary key (metric_id, observation_date) is what makes
-- the pipeline's UPSERT logic possible: it is the constraint that
-- ON CONFLICT checks against.
CREATE TABLE IF NOT EXISTS fact_macro_risk_indicators (
    metric_id         VARCHAR(20)     NOT NULL,
    observation_date  DATE            NOT NULL,
    metric_value      NUMERIC(12, 4)  NOT NULL,
    extracted_at_utc  TIMESTAMP       DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    PRIMARY KEY (metric_id, observation_date)
);

-- Speeds up the date-range scans the dashboard and views below rely on.
CREATE INDEX IF NOT EXISTS idx_macro_date_metric
    ON fact_macro_risk_indicators (observation_date, metric_id);

ALTER TABLE fact_macro_risk_indicators ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- View 1: Systemic Financial Strain (simple version)
-- ============================================================
CREATE OR REPLACE VIEW vw_systemic_financial_strain AS
WITH cc_delinquencies AS (
    SELECT observation_date, metric_value AS credit_card_default_rate
    FROM fact_macro_risk_indicators
    WHERE metric_id = 'DRCCLACBS'
),
prime_rates AS (
    SELECT observation_date, metric_value AS bank_prime_rate
    FROM fact_macro_risk_indicators
    WHERE metric_id = 'MPRIME'
)
SELECT
    cc.observation_date,
    EXTRACT(YEAR FROM cc.observation_date)    AS reporting_year,
    EXTRACT(QUARTER FROM cc.observation_date) AS reporting_quarter,
    cc.credit_card_default_rate,
    pr.bank_prime_rate
FROM cc_delinquencies cc
INNER JOIN prime_rates pr ON cc.observation_date = pr.observation_date;


-- ============================================================
-- View 2: Z-Score Strain Index (stretch goal, optional)
-- ============================================================
CREATE OR REPLACE VIEW vw_systemic_strain_zscore AS
WITH
-- Step 1: Build the daily backbone using only the daily-reporting series.
daily_dates AS (
    SELECT DISTINCT observation_date
    FROM fact_macro_risk_indicators
    WHERE metric_id IN ('MPRIME', 'SOFR90DAYAVG')
),

-- Step 2: Place the raw quarterly delinquency values onto the daily spine.
-- Days when delinquency did not report get NULL here.
delinq_on_daily AS (
    SELECT
        d.observation_date,
        f.metric_value
    FROM daily_dates d
    LEFT JOIN fact_macro_risk_indicators f
        ON  f.observation_date = d.observation_date
        AND f.metric_id = 'DRCCLACBS'
),

-- Step 3: Forward-fill using the group-counter trick.
-- COUNT(metric_value) ignores NULLs by default, so this counter
-- only advances when a real quarterly value is present.
-- Every NULL day between two real readings gets the same counter
-- as the most recent real reading, letting FIRST_VALUE carry it forward.
delinq_grouped AS (
    SELECT
        observation_date,
        metric_value,
        COUNT(metric_value) OVER (ORDER BY observation_date) AS fill_grp
    FROM delinq_on_daily
),

-- Step 4: Materialise the filled delinquency series.
-- Dates before 1991 (where fill_grp = 0 and FIRST_VALUE returns NULL)
-- are excluded, they will simply not contribute to the combined index.
delinq_filled AS (
    SELECT
        observation_date,
        FIRST_VALUE(metric_value) OVER (
            PARTITION BY fill_grp
            ORDER BY observation_date
        ) AS delinquency_value
    FROM delinq_grouped
),

-- Step 5: Combine the forward-filled delinquency values with the two
-- daily series into one unified table, then compute Z-scores.
-- By computing Z-scores here, after the fill, the delinquency mean and
-- standard deviation are calculated across its filled daily series,
-- not just its four raw quarterly points per year.
combined AS (
    SELECT observation_date, 'DRCCLACBS' AS metric_id, delinquency_value AS metric_value
    FROM delinq_filled
    WHERE delinquency_value IS NOT NULL

    UNION ALL

    SELECT observation_date, metric_id, metric_value
    FROM fact_macro_risk_indicators
    WHERE metric_id IN ('MPRIME', 'SOFR90DAYAVG')
),

scored AS (
    SELECT
        observation_date,
        metric_id,
        (metric_value - AVG(metric_value) OVER (PARTITION BY metric_id))
            / NULLIF(STDDEV(metric_value) OVER (PARTITION BY metric_id), 0) AS z_score
    FROM combined
)

SELECT
    observation_date,
    SUM(z_score) AS combined_strain_zscore
FROM scored
GROUP BY observation_date
ORDER BY observation_date;
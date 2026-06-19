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
WITH scored AS (
    SELECT
        metric_id,
        observation_date,
        metric_value,
        (metric_value - AVG(metric_value) OVER (PARTITION BY metric_id))
            / STDDEV(metric_value) OVER (PARTITION BY metric_id) AS z_score
    FROM fact_macro_risk_indicators
    WHERE metric_id IN ('DRCCLACBS', 'MPRIME', 'SOFR90DAYAVG')
)
SELECT
    observation_date,
    SUM(z_score) AS combined_strain_zscore
FROM scored
GROUP BY observation_date
ORDER BY observation_date;
import sys
sys.path.insert(0, 'src')
from config import DATABASE_URL
import pandas as pd
import psycopg2

conn = psycopg2.connect(DATABASE_URL)

queries = {
    "zscore_data.csv": "SELECT * FROM vw_systemic_strain_zscore ORDER BY observation_date;",
    "financial_strain_data.csv": "SELECT * FROM vw_systemic_financial_strain ORDER BY observation_date;",
    "raw_indicators_data.csv": "SELECT * FROM fact_macro_risk_indicators ORDER BY observation_date;",
}

for filename, query in queries.items():
    df = pd.read_sql(query, conn)
    df.to_csv(filename, index=False)
    print(f"{filename}: {len(df)} rows, {df['observation_date'].min()} to {df['observation_date'].max()}")

conn.close()
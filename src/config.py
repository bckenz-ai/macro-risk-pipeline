"""
config.py

Holds the two things every other file needs:
1. The list of FRED metrics this pipeline tracks.
2. The environment variables (API key, database URL) loaded from .env locally,
   or from GitHub Actions secrets in production.

Keeping this in one place means if you ever want to track a new metric,
you only edit this file. Nothing else needs to change.
"""

import os
from dotenv import load_dotenv

# Loads variables from a local .env file. In GitHub Actions, this line does
# nothing harmful: the real values are already injected as environment
# variables by the workflow, so load_dotenv() simply finds no file and skips.
load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Each entry maps a FRED series ID to a human-readable name and its native
# reporting frequency. "frequency" is stored for reference; it does not
# change how the data is fetched, FRED returns whatever frequency the series
# is published at regardless of what we ask for.
METRICS = {
    "SOFR90DAYAVG": {
       "name": "90-Day Average SOFR (Secured Overnight Financing Rate)",
       "frequency": "daily",
   },
    "CPIAUCSL": {
        "name": "Consumer Price Index (All Urban Consumers)",
        "frequency": "monthly",
    },
    "GDPC1": {
        "name": "Real Gross Domestic Product",
        "frequency": "quarterly",
    },
    "DRCCLACBS": {
        "name": "Delinquency Rate on Credit Card Loans, All Commercial Banks",
        "frequency": "quarterly",
    },
    "MPRIME": {
        "name": "Bank Prime Loan Rate",
        "frequency": "daily",
    },
}

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
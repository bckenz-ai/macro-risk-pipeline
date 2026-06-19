"""
fred_client.py

Handles all communication with the FRED API.

Contains the retry-with-exponential-backoff logic.
"""

import logging
import time

import requests
from requests.exceptions import RequestException

from config import FRED_API_KEY, FRED_BASE_URL

logger = logging.getLogger(__name__)


def fetch_series(series_id: str, max_retries: int = 3, base_delay: int = 2) -> list[dict]:
    """
    Fetches every observation for one FRED series ID.

    Returns a list of plain dictionaries, each shaped like:
        {"date": "2026-06-01", "value": "5.33"}

    Note the value is still a string at this point, exactly as FRED returns
    it. Converting it to a real number happens later, in pipeline.py. This
    function's only job is talking to the network reliably.
    """
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
    }

    for attempt in range(max_retries):
        try:
            response = requests.get(FRED_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            observations = payload.get("observations", [])
            logger.info(
                "Fetched %d raw observations for %s", len(observations), series_id
            )
            return observations

        except RequestException as exc:
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt + 1, max_retries, series_id, exc,
            )
            if attempt == max_retries - 1:
                logger.error(
                    "Maximum retries reached for %s. Giving up on this metric.",
                    series_id,
                )
                raise
            # Exponential backoff: 2s, then 4s, then 8s, before giving up.
            time.sleep(base_delay ** (attempt + 1))

    return []
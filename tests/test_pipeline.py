"""
test_pipeline.py

A small, focused test suite. It does not try to test every possible edge
case, it tests the two things that actually matter for this project:

1. Does the cleaning step correctly handle FRED's missing-value marker?
2. Does the retry logic actually retry, instead of crashing on the
   first network error?

Run with: pytest
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from requests.exceptions import RequestException

from pipeline import clean_records
from fred_client import fetch_series


def test_clean_records_drops_missing_values():
    raw = [
        {"date": "2026-06-01", "value": "5.33"},
        {"date": "2026-06-02", "value": "."},  # FRED's missing-value marker
        {"date": "2026-06-03", "value": "5.41"},
    ]

    result = clean_records(raw, "SOFR90DAYAVG")

    assert len(result) == 2
    assert result["metric_id"].iloc[0] == "SOFR90DAYAVG"
    assert pytest.approx(result["metric_value"].iloc[0]) == 5.33


def test_clean_records_handles_empty_input():
    result = clean_records([], "SOFR90DAYAVG")
    assert result.empty


def test_clean_records_converts_types_correctly():
    raw = [{"date": "2026-06-01", "value": "5.33"}]
    result = clean_records(raw, "SOFR90DAYAVG")

    assert pd.api.types.is_float_dtype(result["metric_value"])


@patch("fred_client.requests.get")
@patch("fred_client.time.sleep", return_value=None)  # skip real waiting in tests
def test_fetch_series_retries_then_succeeds(mock_sleep, mock_get):
    failing_response = MagicMock()
    failing_response.raise_for_status.side_effect = RequestException("network blip")

    succeeding_response = MagicMock()
    succeeding_response.raise_for_status.return_value = None
    succeeding_response.json.return_value = {
        "observations": [{"date": "2026-06-01", "value": "5.33"}]
    }

    # First call fails, second call succeeds.
    mock_get.side_effect = [failing_response, succeeding_response]

    result = fetch_series("SOFR90DAYAVG", max_retries=3, base_delay=1)

    assert mock_get.call_count == 2
    assert result == [{"date": "2026-06-01", "value": "5.33"}]


@patch("fred_client.requests.get")
@patch("fred_client.time.sleep", return_value=None)
def test_fetch_series_raises_after_max_retries(mock_sleep, mock_get):
    failing_response = MagicMock()
    failing_response.raise_for_status.side_effect = RequestException("still down")
    mock_get.return_value = failing_response

    with pytest.raises(RequestException):
        fetch_series("SOFR90DAYAVG", max_retries=2, base_delay=1)

    assert mock_get.call_count == 2
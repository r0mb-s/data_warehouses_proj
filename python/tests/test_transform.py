"""Unit tests for app/transform.py (ingestion pipeline)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models import IngestionStats
from app.transform import transform_binance_response, transform_yahoo_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ASSET_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
SOURCE_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")

# A single valid Binance kline row: [open_time_ms, open, high, low, close, volume, ...]
_TS_MS = 1_704_067_200_000  # 2024-01-01 00:00:00 UTC
_BINANCE_ROW = [_TS_MS, "42000.0", "43000.0", "41000.0", "42500.0", "123.45"]


def _yahoo_response(timestamps, opens, highs, lows, closes, volumes):
    return {
        "chart": {
            "result": [{
                "timestamp": timestamps,
                "indicators": {
                    "quote": [{
                        "open": opens,
                        "high": highs,
                        "low": lows,
                        "close": closes,
                        "volume": volumes,
                    }]
                },
            }]
        }
    }


# ---------------------------------------------------------------------------
# transform_binance_response
# ---------------------------------------------------------------------------

def test_transform_binance_basic():
    stats = IngestionStats()
    records = transform_binance_response([_BINANCE_ROW], ASSET_ID, SOURCE_ID, stats)

    assert len(records) == 1
    rec = records[0]
    assert rec.asset_id == ASSET_ID
    assert rec.source_id == SOURCE_ID
    assert rec.metrics["open"] == pytest.approx(42000.0)
    assert rec.metrics["close"] == pytest.approx(42500.0)
    assert rec.metrics["volume"] == pytest.approx(123.45)
    assert rec.event_time.tzinfo is not None
    assert stats.fetched == 1
    assert stats.transformed == 1
    assert stats.skipped == 0


def test_transform_binance_timestamp_conversion():
    stats = IngestionStats()
    records = transform_binance_response([_BINANCE_ROW], ASSET_ID, SOURCE_ID, stats)
    expected = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert records[0].event_time == expected


def test_transform_binance_year_month():
    stats = IngestionStats()
    records = transform_binance_response([_BINANCE_ROW], ASSET_ID, SOURCE_ID, stats)
    ym = records[0].year_month
    assert ym.year == 2024
    assert ym.month == 1
    assert ym.day == 1


def test_transform_binance_invalid_timestamp_skipped():
    bad_row = ["not-a-number", "42000", "43000", "41000", "42500", "1.0"]
    stats = IngestionStats()
    records = transform_binance_response([bad_row], ASSET_ID, SOURCE_ID, stats)
    assert records == []
    assert stats.skipped == 1
    assert stats.transformed == 0


def test_transform_binance_none_metric_omitted():
    row_with_none = [_TS_MS, None, "43000.0", "41000.0", "42500.0", "123.0"]
    stats = IngestionStats()
    records = transform_binance_response([row_with_none], ASSET_ID, SOURCE_ID, stats)
    assert len(records) == 1
    assert "open" not in records[0].metrics
    assert "close" in records[0].metrics


def test_transform_binance_multiple_rows():
    ts2 = _TS_MS + 86_400_000  # next day
    row2 = [ts2, "43000.0", "44000.0", "42000.0", "43500.0", "200.0"]
    stats = IngestionStats()
    records = transform_binance_response([_BINANCE_ROW, row2], ASSET_ID, SOURCE_ID, stats)
    assert len(records) == 2
    assert stats.fetched == 2
    assert stats.transformed == 2


def test_transform_binance_empty_input():
    stats = IngestionStats()
    records = transform_binance_response([], ASSET_ID, SOURCE_ID, stats)
    assert records == []
    assert stats.fetched == 0


# ---------------------------------------------------------------------------
# transform_yahoo_response
# ---------------------------------------------------------------------------

_YAHOO_TS = 1_704_067_200  # 2024-01-01 00:00:00 UTC (seconds, not ms)


def test_transform_yahoo_basic():
    raw = _yahoo_response(
        timestamps=[_YAHOO_TS],
        opens=[42000.0],
        highs=[43000.0],
        lows=[41000.0],
        closes=[42500.0],
        volumes=[1000.0],
    )
    stats = IngestionStats()
    records = transform_yahoo_response(raw, ASSET_ID, SOURCE_ID, stats)

    assert len(records) == 1
    rec = records[0]
    assert rec.metrics["open"] == pytest.approx(42000.0)
    assert rec.metrics["close"] == pytest.approx(42500.0)
    assert rec.event_time == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert stats.transformed == 1
    assert stats.skipped == 0


def test_transform_yahoo_skips_null_timestamp():
    raw = _yahoo_response(
        timestamps=[None, _YAHOO_TS],
        opens=[1.0, 2.0],
        highs=[1.0, 2.0],
        lows=[1.0, 2.0],
        closes=[1.0, 2.0],
        volumes=[1.0, 2.0],
    )
    stats = IngestionStats()
    records = transform_yahoo_response(raw, ASSET_ID, SOURCE_ID, stats)
    assert len(records) == 1
    assert stats.skipped == 1
    assert stats.fetched == 2


def test_transform_yahoo_skips_all_null_metrics():
    raw = _yahoo_response(
        timestamps=[_YAHOO_TS],
        opens=[None],
        highs=[None],
        lows=[None],
        closes=[None],
        volumes=[None],
    )
    stats = IngestionStats()
    records = transform_yahoo_response(raw, ASSET_ID, SOURCE_ID, stats)
    assert records == []
    assert stats.skipped == 1


def test_transform_yahoo_bad_structure_raises():
    with pytest.raises(ValueError, match="Unexpected Yahoo Finance response structure"):
        transform_yahoo_response({}, ASSET_ID, SOURCE_ID, IngestionStats())


def test_transform_yahoo_partial_metrics():
    raw = _yahoo_response(
        timestamps=[_YAHOO_TS],
        opens=[None],
        highs=[None],
        lows=[None],
        closes=[42500.0],
        volumes=[None],
    )
    stats = IngestionStats()
    records = transform_yahoo_response(raw, ASSET_ID, SOURCE_ID, stats)
    assert len(records) == 1
    assert "close" in records[0].metrics
    assert "open" not in records[0].metrics

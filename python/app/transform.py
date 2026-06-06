"""Transform raw API responses into domain records."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from app.models import IngestionStats, TimeSeriesRecord

# Binance kline array indices
_OPEN_TIME = 0
_OPEN = 1
_HIGH = 2
_LOW = 3
_CLOSE = 4
_VOLUME = 5

_METRIC_FIELDS = {
    "open": _OPEN,
    "high": _HIGH,
    "low": _LOW,
    "close": _CLOSE,
    "volume": _VOLUME,
}


def _safe_float(value: Any) -> float | None:
    """Parse a value to float, returning None on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def transform_binance_response(
    raw_data: list[list[Any]],
    asset_id: uuid.UUID,
    source_id: uuid.UUID,
    stats: IngestionStats,
) -> list[TimeSeriesRecord]:
    """Convert raw Binance kline rows into ``TimeSeriesRecord`` objects.

    Updates *stats* in-place to track extraction/transform counts.
    """
    records: list[TimeSeriesRecord] = []
    stats.fetched += len(raw_data)

    for row in raw_data:
        try:
            timestamp_ms = int(row[_OPEN_TIME])
        except (IndexError, TypeError, ValueError):
            stats.skipped += 1
            continue

        event_time = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        year_month = date(event_time.year, event_time.month, 1)

        metrics: dict[str, float] = {}
        for name, idx in _METRIC_FIELDS.items():
            value = _safe_float(row[idx]) if idx < len(row) else None
            if value is not None:
                metrics[name] = value

        records.append(
            TimeSeriesRecord(
                asset_id=asset_id,
                source_id=source_id,
                year_month=year_month,
                event_time=event_time,
                metrics=metrics,
            )
        )
        stats.transformed += 1

    return records


def transform_yahoo_response(
    raw_data: dict[str, Any],
    asset_id: uuid.UUID,
    source_id: uuid.UUID,
    stats: IngestionStats,
) -> list[TimeSeriesRecord]:
    """Convert a Yahoo Finance v8 chart API response into ``TimeSeriesRecord`` objects.

    Yahoo returns parallel arrays rather than row arrays. The ``timestamps``
    array and each metric array share the same index.

    Updates *stats* in-place to track extraction/transform counts.
    """
    try:
        result = raw_data["chart"]["result"][0]
        timestamps: list[int] = result["timestamp"]
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected Yahoo Finance response structure: {exc}") from exc

    opens: list[float | None] = quote.get("open", [])
    highs: list[float | None] = quote.get("high", [])
    lows: list[float | None] = quote.get("low", [])
    closes: list[float | None] = quote.get("close", [])
    volumes: list[float | None] = quote.get("volume", [])

    stats.fetched += len(timestamps)
    records: list[TimeSeriesRecord] = []

    for i, ts in enumerate(timestamps):
        if ts is None:
            stats.skipped += 1
            continue

        event_time = datetime.fromtimestamp(ts, tz=timezone.utc)
        year_month = date(event_time.year, event_time.month, 1)

        metrics: dict[str, float] = {}
        for name, arr in (
            ("open", opens),
            ("high", highs),
            ("low", lows),
            ("close", closes),
            ("volume", volumes),
        ):
            val = _safe_float(arr[i]) if i < len(arr) else None
            if val is not None:
                metrics[name] = val

        if not metrics:
            stats.skipped += 1
            continue

        records.append(
            TimeSeriesRecord(
                asset_id=asset_id,
                source_id=source_id,
                year_month=year_month,
                event_time=event_time,
                metrics=metrics,
            )
        )
        stats.transformed += 1

    return records

"""Pure-Python analytics functions operating on time-series data.

All functions accept plain lists/dicts so they stay decoupled from
Cassandra and FastAPI. The API layer fetches data, then passes it here.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# Aggregations (count, min, max, avg, sum, std-dev)
# ---------------------------------------------------------------------------


def aggregate(values: list[float]) -> dict[str, float | int]:
    """Return count / min / max / mean / sum / stddev for a list of floats."""
    n = len(values)
    if n == 0:
        return {"count": 0, "min": 0, "max": 0, "mean": 0, "sum": 0, "stddev": 0}

    total = sum(values)
    mean = total / n
    variance = sum((v - mean) ** 2 for v in values) / n

    return {
        "count": n,
        "min": min(values),
        "max": max(values),
        "mean": round(mean, 6),
        "sum": round(total, 6),
        "stddev": round(math.sqrt(variance), 6),
    }


# ---------------------------------------------------------------------------
# Trend detection (simple linear regression slope + direction)
# ---------------------------------------------------------------------------


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Return (slope, intercept) via ordinary least squares."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0)

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return 0.0, sum_y / n

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def compute_trend(
    timestamps: list[datetime], values: list[float],
) -> dict:
    """Fit a line and return slope, direction, and percent change."""
    if len(values) < 2:
        return {"slope": 0, "direction": "flat", "pct_change": 0}

    xs = [t.timestamp() for t in timestamps]
    slope, intercept = linear_regression(xs, values)

    first = values[0]
    last = values[-1]
    pct = ((last - first) / first * 100) if first != 0 else 0

    if slope > 0:
        direction = "up"
    elif slope < 0:
        direction = "down"
    else:
        direction = "flat"

    return {
        "slope": round(slope, 10),
        "direction": direction,
        "pct_change": round(pct, 4),
        "start_value": round(first, 6),
        "end_value": round(last, 6),
    }


# ---------------------------------------------------------------------------
# Comparison between two assets
# ---------------------------------------------------------------------------


def compare_assets(
    series_a: list[float], series_b: list[float],
) -> dict:
    """Compare aggregated stats of two value series."""
    agg_a = aggregate(series_a)
    agg_b = aggregate(series_b)

    return {"asset_a": agg_a, "asset_b": agg_b}


# ---------------------------------------------------------------------------
# Simple forecast (linear extrapolation for next N periods)
# ---------------------------------------------------------------------------


def forecast(
    timestamps: list[datetime],
    values: list[float],
    periods: int = 1,
    interval_seconds: float | None = None,
) -> list[dict]:
    """Predict future values via linear extrapolation.

    Args:
        timestamps: Sorted event times.
        values: Corresponding metric values.
        periods: How many future data points to predict.
        interval_seconds: Gap between data points.  Auto-detected if None.
    """
    if len(values) < 2:
        return []

    xs = [t.timestamp() for t in timestamps]
    slope, intercept = linear_regression(xs, values)

    if interval_seconds is None and len(xs) >= 2:
        gaps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        interval_seconds = sum(gaps) / len(gaps)

    predictions = []
    last_ts = xs[-1]
    for i in range(1, periods + 1):
        future_ts = last_ts + interval_seconds * i
        predicted = slope * future_ts + intercept
        predictions.append({
            "event_time": datetime.fromtimestamp(future_ts, tz=timezone.utc).isoformat(),
            "predicted_value": round(predicted, 6),
            "period": i,
        })

    return predictions


# ---------------------------------------------------------------------------
# Risk signals (volatility, drawdown, daily-return stats)
# ---------------------------------------------------------------------------


def compute_risk(values: list[float]) -> dict:
    """Compute basic risk metrics from a price series."""
    if len(values) < 2:
        return {
            "volatility": 0,
            "max_drawdown_pct": 0,
            "avg_daily_return_pct": 0,
            "sharpe_approx": 0,
        }

    # Daily returns
    returns = [(values[i] - values[i - 1]) / values[i - 1]
               for i in range(1, len(values)) if values[i - 1] != 0]

    if not returns:
        return {"volatility": 0, "max_drawdown_pct": 0, "avg_daily_return_pct": 0, "sharpe_approx": 0}

    avg_ret = sum(returns) / len(returns)
    variance = sum((r - avg_ret) ** 2 for r in returns) / len(returns)
    volatility = math.sqrt(variance)

    # Max drawdown
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak != 0 else 0
        if dd > max_dd:
            max_dd = dd

    # Simplified Sharpe (assuming risk-free rate = 0)
    sharpe = (avg_ret / volatility) if volatility != 0 else 0

    return {
        "volatility": round(volatility, 6),
        "max_drawdown_pct": round(max_dd * 100, 4),
        "avg_daily_return_pct": round(avg_ret * 100, 6),
        "sharpe_approx": round(sharpe, 4),
    }

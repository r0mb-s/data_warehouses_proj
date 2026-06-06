"""Unit tests for app/analytics.py pure functions."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from app.analytics import (
    aggregate,
    compare_assets,
    compute_risk,
    compute_trend,
    forecast,
    linear_regression,
)


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------

def test_aggregate_empty():
    result = aggregate([])
    assert result == {"count": 0, "min": 0, "max": 0, "mean": 0, "sum": 0, "stddev": 0}


def test_aggregate_single_value():
    result = aggregate([5.0])
    assert result["count"] == 1
    assert result["min"] == 5.0
    assert result["max"] == 5.0
    assert result["mean"] == 5.0
    assert result["sum"] == 5.0
    assert result["stddev"] == 0.0


def test_aggregate_known_values():
    # values: 1, 2, 3, 4, 5  →  mean=3, sum=15, stddev=sqrt(2)≈1.414214
    result = aggregate([1.0, 2.0, 3.0, 4.0, 5.0])
    assert result["count"] == 5
    assert result["min"] == 1.0
    assert result["max"] == 5.0
    assert result["mean"] == pytest.approx(3.0, rel=1e-5)
    assert result["sum"] == pytest.approx(15.0, rel=1e-5)
    assert result["stddev"] == pytest.approx(math.sqrt(2), rel=1e-4)


def test_aggregate_rounds_to_six_decimals():
    result = aggregate([1.0 / 3.0])
    assert len(str(result["mean"]).split(".")[-1]) <= 6


# ---------------------------------------------------------------------------
# linear_regression
# ---------------------------------------------------------------------------

def test_linear_regression_perfect_fit():
    # y = 2x + 1
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [3.0, 5.0, 7.0, 9.0, 11.0]
    slope, intercept = linear_regression(xs, ys)
    assert slope == pytest.approx(2.0, rel=1e-6)
    assert intercept == pytest.approx(1.0, rel=1e-6)


def test_linear_regression_single_point():
    slope, intercept = linear_regression([1.0], [4.0])
    assert slope == 0.0
    assert intercept == 4.0


def test_linear_regression_constant_x():
    # Denominator is zero → returns 0 slope, mean y
    slope, intercept = linear_regression([1.0, 1.0, 1.0], [2.0, 4.0, 6.0])
    assert slope == 0.0
    assert intercept == pytest.approx(4.0, rel=1e-6)


# ---------------------------------------------------------------------------
# compute_trend
# ---------------------------------------------------------------------------

def _make_timestamps(n: int, step_days: int = 1) -> list[datetime]:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta
    return [base + timedelta(days=i * step_days) for i in range(n)]


def test_compute_trend_up():
    ts = _make_timestamps(5)
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = compute_trend(ts, values)
    assert result["direction"] == "up"
    assert result["slope"] > 0
    assert result["pct_change"] == pytest.approx(400.0, rel=1e-3)
    assert result["start_value"] == 1.0
    assert result["end_value"] == 5.0


def test_compute_trend_down():
    ts = _make_timestamps(5)
    values = [5.0, 4.0, 3.0, 2.0, 1.0]
    result = compute_trend(ts, values)
    assert result["direction"] == "down"
    assert result["slope"] < 0


def test_compute_trend_flat():
    ts = _make_timestamps(4)
    values = [3.0, 3.0, 3.0, 3.0]
    result = compute_trend(ts, values)
    assert result["direction"] == "flat"
    assert result["pct_change"] == 0.0


def test_compute_trend_single_value():
    ts = _make_timestamps(1)
    result = compute_trend(ts, [42.0])
    assert result["direction"] == "flat"
    assert result["slope"] == 0


# ---------------------------------------------------------------------------
# forecast
# ---------------------------------------------------------------------------

def test_forecast_returns_n_periods():
    ts = _make_timestamps(10)
    values = [float(i) for i in range(10)]
    result = forecast(ts, values, periods=7)
    assert len(result) == 7
    for i, point in enumerate(result, start=1):
        assert point["period"] == i
        assert "event_time" in point
        assert "predicted_value" in point


def test_forecast_short_series_returns_empty():
    ts = _make_timestamps(1)
    assert forecast(ts, [1.0], periods=5) == []


def test_forecast_monotone_increasing():
    # For perfectly increasing data the next value should be > last observed
    ts = _make_timestamps(5)
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = forecast(ts, values, periods=3)
    assert result[0]["predicted_value"] > 5.0


# ---------------------------------------------------------------------------
# compute_risk
# ---------------------------------------------------------------------------

def test_compute_risk_short_series_returns_zeros():
    result = compute_risk([100.0])
    assert result == {"volatility": 0, "max_drawdown_pct": 0, "avg_daily_return_pct": 0, "sharpe_approx": 0}


def test_compute_risk_no_change_series():
    result = compute_risk([100.0, 100.0, 100.0, 100.0])
    assert result["volatility"] == 0.0
    assert result["max_drawdown_pct"] == 0.0
    assert result["avg_daily_return_pct"] == 0.0


def test_compute_risk_drawdown():
    # Peak 100 → drops to 50 → 50% drawdown
    values = [100.0, 90.0, 80.0, 70.0, 50.0]
    result = compute_risk(values)
    assert result["max_drawdown_pct"] == pytest.approx(50.0, rel=1e-4)


def test_compute_risk_keys_present():
    result = compute_risk([100.0, 110.0, 105.0, 115.0])
    assert set(result.keys()) == {"volatility", "max_drawdown_pct", "avg_daily_return_pct", "sharpe_approx"}


# ---------------------------------------------------------------------------
# compare_assets
# ---------------------------------------------------------------------------

def test_compare_assets_structure():
    result = compare_assets([1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
    assert "asset_a" in result
    assert "asset_b" in result
    assert result["asset_a"]["mean"] == pytest.approx(2.0, rel=1e-5)
    assert result["asset_b"]["mean"] == pytest.approx(20.0, rel=1e-5)


def test_compare_assets_empty():
    result = compare_assets([], [])
    assert result["asset_a"]["count"] == 0
    assert result["asset_b"]["count"] == 0

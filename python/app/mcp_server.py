"""MCP server exposing the data warehouse capabilities as tools.

Run with:
    mcp-serve          (console script)
    python -m app.mcp_server
"""

from __future__ import annotations

import uuid
from datetime import datetime

from cassandra.cluster import Cluster, Session
from mcp.server.fastmcp import FastMCP

from app import analytics
from app.config import settings

KS = settings.keyspace

mcp = FastMCP("data-warehouse")

# ---------------------------------------------------------------------------
# Cassandra connection (lazy; initialised on first tool call)
# ---------------------------------------------------------------------------

_cluster = None
_session: Session | None = None


def _get_session() -> Session:
    global _cluster, _session
    if _session is None:
        _cluster = Cluster([settings.cassandra_host], port=settings.cassandra_port)
        _session = _cluster.connect()
    return _session


def _coerce_year_month(raw) -> str:
    if hasattr(raw, "date"):
        return str(raw.date())
    return str(raw)


def _fetch_metric_series(
    asset_id: str, source_id: str, metric: str
) -> tuple[list[datetime], list[float]]:
    aid = uuid.UUID(asset_id)
    sid = uuid.UUID(source_id)
    rows = list(
        _get_session().execute(
            f"SELECT event_time, metrics FROM {KS}.time_series_data "
            "WHERE asset_id = %s AND source_id = %s ALLOW FILTERING",
            (aid, sid),
        )
    )
    pairs = []
    for r in rows:
        m = r.metrics or {}
        if metric in m:
            pairs.append((r.event_time, m[metric]))
    pairs.sort(key=lambda p: p[0])
    return [p[0] for p in pairs], [p[1] for p in pairs]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_assets() -> list[dict]:
    """List all financial assets available in the data warehouse.

    Returns each asset's id, symbol, asset class, and region.
    Use the returned asset_id and source_id to call other tools.
    """
    rows = _get_session().execute(
        f"SELECT asset_id, valid_from, symbol, asset_class, region, source_id, is_deleted "
        f"FROM {KS}.asset_details"
    )
    seen: dict[str, dict] = {}
    for r in rows:
        key = str(r.asset_id)
        if key not in seen:
            seen[key] = {
                "asset_id": str(r.asset_id),
                "symbol": r.symbol,
                "asset_class": r.asset_class,
                "region": r.region,
                "source_id": str(r.source_id) if r.source_id else None,
                "is_deleted": r.is_deleted,
            }
    return list(seen.values())


@mcp.tool()
def list_sources() -> list[dict]:
    """List all data sources (providers) registered in the data warehouse."""
    rows = _get_session().execute(
        f"SELECT source_id, name, api_url, description, is_deleted FROM {KS}.data_sources"
    )
    return [
        {
            "source_id": str(r.source_id),
            "name": r.name,
            "api_url": r.api_url,
            "description": r.description,
            "is_deleted": r.is_deleted,
        }
        for r in rows
    ]


@mcp.tool()
def fetch_time_series(asset_id: str, source_id: str, metric: str = "close") -> list[dict]:
    """Fetch time-series OHLCV data for a specific asset and data source.

    Args:
        asset_id: UUID of the asset (from list_assets)
        source_id: UUID of the data source (from list_assets or list_sources)
        metric: Which metric to include prominently. One of: open, high, low, close, volume.

    Returns a list of records sorted by event_time, each with event_time and all metrics.
    """
    aid = uuid.UUID(asset_id)
    sid = uuid.UUID(source_id)
    rows = list(
        _get_session().execute(
            f"SELECT event_time, metrics FROM {KS}.time_series_data "
            "WHERE asset_id = %s AND source_id = %s ALLOW FILTERING",
            (aid, sid),
        )
    )
    rows.sort(key=lambda r: r.event_time)
    return [
        {
            "event_time": r.event_time.isoformat(),
            **(r.metrics or {}),
        }
        for r in rows
    ]


@mcp.tool()
def get_aggregation(asset_id: str, source_id: str, metric: str = "close") -> dict:
    """Compute count, min, max, mean, sum, and stddev for an asset metric.

    Args:
        asset_id: UUID of the asset
        source_id: UUID of the data source
        metric: Metric to aggregate. One of: open, high, low, close, volume.
    """
    timestamps, values = _fetch_metric_series(asset_id, source_id, metric)
    if not values:
        return {"error": "No data found for this asset/source/metric combination"}
    return {"asset_id": asset_id, "metric": metric, **analytics.aggregate(values)}


@mcp.tool()
def get_trend(asset_id: str, source_id: str, metric: str = "close") -> dict:
    """Compute the price trend for an asset: direction (up/down/flat), slope, and percent change.

    Args:
        asset_id: UUID of the asset
        source_id: UUID of the data source
        metric: Metric to analyse. One of: open, high, low, close, volume.
    """
    timestamps, values = _fetch_metric_series(asset_id, source_id, metric)
    if len(values) < 2:
        return {"error": "Not enough data points for trend analysis (need at least 2)"}
    return {"asset_id": asset_id, "metric": metric, **analytics.compute_trend(timestamps, values)}


@mcp.tool()
def get_forecast(
    asset_id: str, source_id: str, metric: str = "close", periods: int = 7
) -> dict:
    """Forecast future values for an asset metric using linear extrapolation.

    Args:
        asset_id: UUID of the asset
        source_id: UUID of the data source
        metric: Metric to forecast. One of: open, high, low, close, volume.
        periods: Number of future periods to predict (default 7).
    """
    timestamps, values = _fetch_metric_series(asset_id, source_id, metric)
    if len(values) < 2:
        return {"error": "Not enough data points for forecasting (need at least 2)"}
    predictions = analytics.forecast(timestamps, values, periods=periods)
    return {"asset_id": asset_id, "metric": metric, "predictions": predictions}


@mcp.tool()
def get_risk(asset_id: str, source_id: str, metric: str = "close") -> dict:
    """Compute risk signals for an asset: volatility, max drawdown, avg daily return, Sharpe ratio.

    Args:
        asset_id: UUID of the asset
        source_id: UUID of the data source
        metric: Metric to analyse. Typically 'close'.
    """
    _, values = _fetch_metric_series(asset_id, source_id, metric)
    if len(values) < 2:
        return {"error": "Not enough data points for risk analysis (need at least 2)"}
    return {"asset_id": asset_id, "metric": metric, **analytics.compute_risk(values)}


@mcp.tool()
def compare_assets(
    asset_a_id: str,
    asset_a_source_id: str,
    asset_b_id: str,
    asset_b_source_id: str,
    metric: str = "close",
) -> dict:
    """Side-by-side aggregation comparison of two assets on the same metric.

    Args:
        asset_a_id: UUID of the first asset
        asset_a_source_id: UUID of the first asset's data source
        asset_b_id: UUID of the second asset
        asset_b_source_id: UUID of the second asset's data source
        metric: Metric to compare. One of: open, high, low, close, volume.
    """
    _, values_a = _fetch_metric_series(asset_a_id, asset_a_source_id, metric)
    _, values_b = _fetch_metric_series(asset_b_id, asset_b_source_id, metric)
    if not values_a or not values_b:
        return {"error": "No data found for one or both assets"}
    return {
        "metric": metric,
        "asset_a": {"asset_id": asset_a_id, **analytics.aggregate(values_a)},
        "asset_b": {"asset_id": asset_b_id, **analytics.aggregate(values_b)},
    }


@mcp.tool()
def summarize_asset(asset_id: str, source_id: str, metric: str = "close") -> dict:
    """Agentic tool: fetch full analytics for an asset and return a structured summary.

    Chains get_aggregation, get_trend, get_risk, and get_forecast (7 periods) into
    one comprehensive result. Use this to answer questions like 'tell me about BTC'
    or 'what is the outlook for this asset'.

    Args:
        asset_id: UUID of the asset
        source_id: UUID of the data source
        metric: Primary metric to analyse (default 'close').
    """
    timestamps, values = _fetch_metric_series(asset_id, source_id, metric)
    if len(values) < 2:
        return {"error": "Not enough data to summarize this asset"}

    agg = analytics.aggregate(values)
    trend = analytics.compute_trend(timestamps, values)
    risk = analytics.compute_risk(values)
    forecast = analytics.forecast(timestamps, values, periods=7)

    # Resolve symbol from asset_details
    rows = list(
        _get_session().execute(
            f"SELECT symbol, asset_class, region FROM {KS}.asset_details "
            "WHERE asset_id = %s LIMIT 1",
            (uuid.UUID(asset_id),),
        )
    )
    symbol = rows[0].symbol if rows else "unknown"
    asset_class = rows[0].asset_class if rows else "unknown"

    return {
        "asset_id": asset_id,
        "symbol": symbol,
        "asset_class": asset_class,
        "metric": metric,
        "data_points": agg["count"],
        "aggregation": agg,
        "trend": trend,
        "risk": risk,
        "forecast_next_7_periods": forecast,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

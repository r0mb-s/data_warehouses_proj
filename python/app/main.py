"""FastAPI application serving the data warehouse REST API."""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import AsyncIterator

import uvicorn
from cassandra.cluster import Cluster, Session
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app import analytics
from app.config import settings
from app.extract import Extractor
from app.models import IngestionStats
from app.schemas import (
    AggregationResponse,
    AnalyticsRequest,
    AssetByClassResponse,
    AssetDetailsResponse,
    CompareRequest,
    CompareResponse,
    CreateAssetByClass,
    CreateAssetDetails,
    CreateDataSource,
    CreateTimeSeries,
    DataSourceResponse,
    ExportRequest,
    ForecastPoint,
    ForecastRequest,
    ForecastResponse,
    IngestRequest,
    IngestResponse,
    RiskResponse,
    TimeSeriesResponse,
    TrendResponse,
    ChatRequest,
    ChatResponse,
)
from app.transform import transform_binance_response, transform_yahoo_response
from app.assistant import chat_once

logger = logging.getLogger(__name__)

KS = settings.keyspace


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_session: Session | None = None


def _get_session() -> Session:
    if _session is None:
        raise RuntimeError("Database session is not initialised")
    return _session


def _query(cql: str, params: tuple | None = None) -> list:
    """Execute a CQL query and return the result rows as a list."""
    try:
        return list(_get_session().execute(cql, params))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc


def _execute(cql: str, params: tuple) -> None:
    """Execute a CQL mutation (INSERT/UPDATE/DELETE)."""
    try:
        _get_session().execute(cql, params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB error: {exc}") from exc


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _session

    cluster = Cluster([settings.cassandra_host], port=settings.cassandra_port)
    _session = cluster.connect()
    logger.info("Connected to Cassandra at %s:%s", settings.cassandra_host, settings.cassandra_port)

    yield

    _session.shutdown()
    cluster.shutdown()
    _session = None
    logger.info("Cassandra connection closed")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Data Warehouse API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)


# ---------------------------------------------------------------------------
# Data Sources
# ---------------------------------------------------------------------------


@app.get("/sources", response_model=list[DataSourceResponse])
async def get_data_sources() -> list[DataSourceResponse]:
    rows = _query(
        f"SELECT source_id, api_url, description, is_deleted, name FROM {KS}.data_sources"
    )
    return [
        DataSourceResponse(
            source_id=r.source_id,
            api_url=r.api_url,
            description=r.description,
            is_deleted=r.is_deleted,
            name=r.name,
        )
        for r in rows
    ]


@app.get("/sources/{source_id}", response_model=DataSourceResponse)
async def get_data_source(source_id: uuid.UUID) -> DataSourceResponse:
    rows = _query(
        f"SELECT source_id, api_url, description, is_deleted, name FROM {KS}.data_sources "
        "WHERE source_id = %s",
        (source_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Data source not found")
    r = rows[0]
    return DataSourceResponse(
        source_id=r.source_id,
        api_url=r.api_url,
        description=r.description,
        is_deleted=r.is_deleted,
        name=r.name,
    )


@app.post("/sources", status_code=201)
async def create_data_source(payload: CreateDataSource) -> uuid.UUID:
    new_id = uuid.uuid4()
    _execute(
        f"INSERT INTO {KS}.data_sources (source_id, api_url, description, is_deleted, name) "
        "VALUES (%s, %s, %s, %s, %s)",
        (new_id, payload.api_url, payload.description, False, payload.name),
    )
    return new_id


@app.delete("/sources/{source_id}", status_code=200)
async def delete_data_source(source_id: uuid.UUID) -> dict:
    """Soft-delete a data source by setting is_deleted=True."""
    rows = _query(
        f"SELECT source_id FROM {KS}.data_sources WHERE source_id = %s",
        (source_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Data source not found")
    _execute(
        f"UPDATE {KS}.data_sources SET is_deleted = true WHERE source_id = %s",
        (source_id,),
    )
    return {"source_id": source_id, "is_deleted": True}


# ---------------------------------------------------------------------------
# Asset Details
# ---------------------------------------------------------------------------


@app.get("/assets", response_model=list[AssetDetailsResponse])
async def get_asset_details() -> list[AssetDetailsResponse]:
    rows = _query(
        f"SELECT asset_id, valid_from, asset_class, description, "
        f"is_deleted, region, source_id, symbol FROM {KS}.asset_details"
    )
    return [
        AssetDetailsResponse(
            asset_id=r.asset_id,
            valid_from=r.valid_from,
            asset_class=r.asset_class,
            description=r.description,
            is_deleted=r.is_deleted,
            region=r.region,
            source_id=r.source_id,
            symbol=r.symbol,
        )
        for r in rows
    ]


@app.get("/assets/{asset_id}")
async def get_asset_by_id(
    asset_id: uuid.UUID,
    as_of: str | None = Query(None, description="ISO 8601 datetime. Returns the single version valid at that timestamp."),
) -> list[AssetDetailsResponse] | AssetDetailsResponse:
    """Return SCD Type 2 versions of an asset.

    Without as_of: all versions, newest first.
    With as_of: the single version valid at that timestamp (point-in-time query).
    """
    if as_of is not None:
        try:
            as_of_dt = datetime.fromisoformat(as_of)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid as_of format. Use ISO 8601: {exc}") from exc
        rows = _query(
            f"SELECT asset_id, valid_from, asset_class, description, "
            f"is_deleted, region, source_id, symbol FROM {KS}.asset_details "
            "WHERE asset_id = %s AND valid_from <= %s LIMIT 1",
            (asset_id, as_of_dt),
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"No asset version found valid at {as_of}")
        r = rows[0]
        return AssetDetailsResponse(
            asset_id=r.asset_id,
            valid_from=r.valid_from,
            asset_class=r.asset_class,
            description=r.description,
            is_deleted=r.is_deleted,
            region=r.region,
            source_id=r.source_id,
            symbol=r.symbol,
        )

    rows = _query(
        f"SELECT asset_id, valid_from, asset_class, description, "
        f"is_deleted, region, source_id, symbol FROM {KS}.asset_details "
        "WHERE asset_id = %s",
        (asset_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Asset not found")
    return [
        AssetDetailsResponse(
            asset_id=r.asset_id,
            valid_from=r.valid_from,
            asset_class=r.asset_class,
            description=r.description,
            is_deleted=r.is_deleted,
            region=r.region,
            source_id=r.source_id,
            symbol=r.symbol,
        )
        for r in rows
    ]


@app.post("/assets", status_code=201)
async def create_asset_details(payload: CreateAssetDetails) -> dict:
    asset_id = payload.asset_id or uuid.uuid4()
    valid_from = datetime.now(timezone.utc)
    _execute(
        f"INSERT INTO {KS}.asset_details "
        "(asset_id, valid_from, asset_class, description, is_deleted, region, source_id, symbol) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (asset_id, valid_from, payload.asset_class, payload.description, False,
         payload.region, payload.source_id, payload.symbol),
    )
    return {"asset_id": asset_id, "valid_from": valid_from}


@app.delete("/assets/{asset_id}", status_code=200)
async def delete_asset_details(asset_id: uuid.UUID) -> dict:
    """Soft-delete an asset by inserting a new SCD Type 2 version with is_deleted=True."""
    rows = _query(
        f"SELECT asset_id, asset_class, description, region, source_id, symbol "
        f"FROM {KS}.asset_details WHERE asset_id = %s LIMIT 1",
        (asset_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Asset not found")
    r = rows[0]
    valid_from = datetime.now(timezone.utc)
    _execute(
        f"INSERT INTO {KS}.asset_details "
        "(asset_id, valid_from, asset_class, description, is_deleted, region, source_id, symbol) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (asset_id, valid_from, r.asset_class, r.description, True,
         r.region, r.source_id, r.symbol),
    )
    return {"asset_id": asset_id, "valid_from": valid_from, "is_deleted": True}


# ---------------------------------------------------------------------------
# Assets by Class
# ---------------------------------------------------------------------------


@app.get("/assets-by-class", response_model=list[AssetByClassResponse])
async def get_assets_by_class() -> list[AssetByClassResponse]:
    rows = _query(
        f"SELECT asset_class, asset_id, description, region, symbol FROM {KS}.assets_by_class"
    )
    return [
        AssetByClassResponse(
            asset_class=r.asset_class,
            asset_id=r.asset_id,
            description=r.description,
            region=r.region,
            symbol=r.symbol,
        )
        for r in rows
    ]


@app.post("/assets-by-class", status_code=201)
async def create_asset_by_class(payload: CreateAssetByClass) -> dict:
    asset_id = payload.asset_id or uuid.uuid4()
    _execute(
        f"INSERT INTO {KS}.assets_by_class "
        "(asset_class, asset_id, description, region, symbol) "
        "VALUES (%s, %s, %s, %s, %s)",
        (payload.asset_class, asset_id, payload.description, payload.region, payload.symbol),
    )
    return {"asset_class": payload.asset_class, "asset_id": asset_id}


# ---------------------------------------------------------------------------
# Time Series
# ---------------------------------------------------------------------------


def _coerce_year_month(raw) -> date:
    """Convert a cassandra.util.Date to a Python date."""
    if hasattr(raw, "date"):
        return raw.date()
    return date.fromisoformat(str(raw))


@app.get("/time-series", response_model=list[TimeSeriesResponse])
async def get_time_series(
    asset_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
) -> list[TimeSeriesResponse]:
    """Return time-series records. Filter by asset_id and/or source_id when provided."""
    if asset_id is not None and source_id is not None:
        rows = _query(
            f"SELECT asset_id, source_id, year_month, event_time, metrics FROM {KS}.time_series_data "
            "WHERE asset_id = %s AND source_id = %s ALLOW FILTERING",
            (asset_id, source_id),
        )
    elif asset_id is not None:
        rows = _query(
            f"SELECT asset_id, source_id, year_month, event_time, metrics FROM {KS}.time_series_data "
            "WHERE asset_id = %s ALLOW FILTERING",
            (asset_id,),
        )
    else:
        rows = _query(
            f"SELECT asset_id, source_id, year_month, event_time, metrics FROM {KS}.time_series_data"
        )
    return [
        TimeSeriesResponse(
            asset_id=r.asset_id,
            source_id=r.source_id,
            year_month=_coerce_year_month(r.year_month),
            event_time=r.event_time,
            metrics=r.metrics or {},
        )
        for r in rows
    ]


@app.post("/time-series", status_code=201)
async def create_time_series(payload: CreateTimeSeries) -> dict:
    _execute(
        f"INSERT INTO {KS}.time_series_data "
        "(asset_id, source_id, year_month, event_time, metrics) "
        "VALUES (%s, %s, %s, %s, %s)",
        (payload.asset_id, payload.source_id, payload.year_month,
         payload.event_time, payload.metrics),
    )
    return {"asset_id": payload.asset_id, "source_id": payload.source_id, "event_time": payload.event_time}


# ---------------------------------------------------------------------------
# Ingestion Pipeline
# ---------------------------------------------------------------------------


@app.post("/ingest", response_model=IngestResponse)
async def ingest(payload: IngestRequest) -> IngestResponse:
    """Run extract -> transform -> load for a symbol and register the asset."""
    session = _get_session()
    stats = IngestionStats()
    asset_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    desc = payload.description or f"{payload.symbol} via {(payload.provider or 'binance').capitalize()}"

    # Extract + Transform (dispatch by provider)
    extractor = Extractor()
    try:
        provider = (payload.provider or "binance").lower()
        if provider == "yahoo":
            raw_data = await extractor.fetch_yahoo_data(payload.symbol, payload.interval)
            records = transform_yahoo_response(raw_data, asset_id, payload.source_id, stats)
        elif provider == "binance":
            raw_data = await extractor.fetch_binance_data(payload.symbol, payload.interval)
            records = transform_binance_response(raw_data, asset_id, payload.source_id, stats)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'. Use 'binance' or 'yahoo'.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from {provider}: {exc}") from exc
    finally:
        await extractor.close()

    # Load time series
    ts_cql = (
        f"INSERT INTO {KS}.time_series_data "
        "(asset_id, source_id, year_month, event_time, metrics) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    for record in records:
        try:
            session.execute(ts_cql, (
                record.asset_id, record.source_id, record.year_month,
                record.event_time, record.metrics,
            ))
            stats.stored += 1
        except Exception:
            logger.exception("Failed to insert time-series record")
            stats.failures += 1

    # Register in asset_details (SCD Type 2)
    _execute(
        f"INSERT INTO {KS}.asset_details "
        "(asset_id, valid_from, asset_class, description, is_deleted, region, source_id, symbol) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (asset_id, now, payload.asset_class, desc, False, payload.region, payload.source_id, payload.symbol),
    )

    # Register in assets_by_class
    _execute(
        f"INSERT INTO {KS}.assets_by_class "
        "(asset_class, asset_id, description, region, symbol) "
        "VALUES (%s, %s, %s, %s, %s)",
        (payload.asset_class, asset_id, desc, payload.region, payload.symbol),
    )

    return IngestResponse(
        asset_id=asset_id,
        symbol=payload.symbol,
        fetched=stats.fetched,
        transformed=stats.transformed,
        stored=stats.stored,
        skipped=stats.skipped,
        failures=stats.failures,
    )


# ---------------------------------------------------------------------------
# Shared: fetch metric series for an asset
# ---------------------------------------------------------------------------


def _fetch_metric_series(
    asset_id: uuid.UUID, source_id: uuid.UUID, metric: str,
) -> tuple[list[datetime], list[float]]:
    """Return sorted (timestamps, values) for a given asset+metric."""
    rows = _query(
        f"SELECT event_time, metrics FROM {KS}.time_series_data "
        "WHERE asset_id = %s AND source_id = %s ALLOW FILTERING",
        (asset_id, source_id),
    )
    pairs = []
    for r in rows:
        m = r.metrics or {}
        if metric in m:
            pairs.append((r.event_time, m[metric]))

    pairs.sort(key=lambda p: p[0])
    timestamps = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    return timestamps, values


# ---------------------------------------------------------------------------
# Analytics: Aggregations
# ---------------------------------------------------------------------------


@app.post("/analytics/aggregate", response_model=AggregationResponse)
async def analytics_aggregate(payload: AnalyticsRequest) -> AggregationResponse:
    """Compute count/min/max/mean/sum/stddev for a metric."""
    _, values = _fetch_metric_series(payload.asset_id, payload.source_id, payload.metric)
    if not values:
        raise HTTPException(status_code=404, detail="No data found for this asset/metric")

    agg = analytics.aggregate(values)
    return AggregationResponse(asset_id=payload.asset_id, metric=payload.metric, **agg)


# ---------------------------------------------------------------------------
# Analytics: Trend
# ---------------------------------------------------------------------------


@app.post("/analytics/trend", response_model=TrendResponse)
async def analytics_trend(payload: AnalyticsRequest) -> TrendResponse:
    """Detect price trend (direction, slope, percent change)."""
    timestamps, values = _fetch_metric_series(payload.asset_id, payload.source_id, payload.metric)
    if len(values) < 2:
        raise HTTPException(status_code=404, detail="Not enough data for trend analysis")

    trend = analytics.compute_trend(timestamps, values)
    return TrendResponse(asset_id=payload.asset_id, metric=payload.metric, **trend)


# ---------------------------------------------------------------------------
# Analytics: Forecast
# ---------------------------------------------------------------------------


@app.post("/analytics/forecast", response_model=ForecastResponse)
async def analytics_forecast(payload: ForecastRequest) -> ForecastResponse:
    """Predict future values via linear extrapolation."""
    timestamps, values = _fetch_metric_series(payload.asset_id, payload.source_id, payload.metric)
    if len(values) < 2:
        raise HTTPException(status_code=404, detail="Not enough data for forecasting")

    predictions = analytics.forecast(timestamps, values, periods=payload.periods)
    return ForecastResponse(
        asset_id=payload.asset_id,
        metric=payload.metric,
        predictions=[ForecastPoint(**p) for p in predictions],
    )


# ---------------------------------------------------------------------------
# Analytics: Risk
# ---------------------------------------------------------------------------


@app.post("/analytics/risk", response_model=RiskResponse)
async def analytics_risk(payload: AnalyticsRequest) -> RiskResponse:
    """Compute volatility, max drawdown, Sharpe ratio approximation."""
    _, values = _fetch_metric_series(payload.asset_id, payload.source_id, payload.metric)
    if len(values) < 2:
        raise HTTPException(status_code=404, detail="Not enough data for risk analysis")

    risk = analytics.compute_risk(values)
    return RiskResponse(asset_id=payload.asset_id, metric=payload.metric, **risk)


# ---------------------------------------------------------------------------
# Analytics: Compare two assets
# ---------------------------------------------------------------------------


@app.post("/analytics/compare", response_model=CompareResponse)
async def analytics_compare(payload: CompareRequest) -> CompareResponse:
    """Side-by-side aggregation comparison of two assets."""
    _, values_a = _fetch_metric_series(payload.asset_a_id, payload.asset_a_source_id, payload.metric)
    _, values_b = _fetch_metric_series(payload.asset_b_id, payload.asset_b_source_id, payload.metric)

    if not values_a or not values_b:
        raise HTTPException(status_code=404, detail="Not enough data for one or both assets")

    agg_a = analytics.aggregate(values_a)
    agg_b = analytics.aggregate(values_b)

    return CompareResponse(
        metric=payload.metric,
        asset_a=AggregationResponse(asset_id=payload.asset_a_id, metric=payload.metric, **agg_a),
        asset_b=AggregationResponse(asset_id=payload.asset_b_id, metric=payload.metric, **agg_b),
    )


# ---------------------------------------------------------------------------
# Export: Spark-compatible data export (JSON-lines or CSV)
# ---------------------------------------------------------------------------


@app.post("/export")
async def export_data(payload: ExportRequest) -> StreamingResponse:
    """Export time-series data in a Spark-ingestible format.

    Supported formats:
    - ``jsonl``: One JSON object per line (ideal for ``spark.read.json()``)
    - ``csv``: Header row + data rows (ideal for ``spark.read.csv()``)
    """
    rows = _query(
        f"SELECT asset_id, source_id, year_month, event_time, metrics "
        f"FROM {KS}.time_series_data "
        "WHERE asset_id = %s AND source_id = %s ALLOW FILTERING",
        (payload.asset_id, payload.source_id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="No data found")

    # Flatten each row into a dict with metrics unpacked as top-level columns
    flat_rows = []
    for r in rows:
        entry = {
            "asset_id": str(r.asset_id),
            "source_id": str(r.source_id),
            "year_month": str(_coerce_year_month(r.year_month)),
            "event_time": r.event_time.isoformat() if r.event_time else "",
        }
        for k, v in (r.metrics or {}).items():
            entry[k] = v
        flat_rows.append(entry)

    flat_rows.sort(key=lambda x: x["event_time"])

    if payload.format == "csv":
        buf = io.StringIO()
        if flat_rows:
            writer = csv.DictWriter(buf, fieldnames=flat_rows[0].keys())
            writer.writeheader()
            writer.writerows(flat_rows)
        content = buf.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"},
        )

    # Default: JSON-lines
    lines = [json.dumps(row) for row in flat_rows]
    content = "\n".join(lines) + "\n"
    return StreamingResponse(
        iter([content]),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=export.jsonl"},
    )


# ---------------------------------------------------------------------------
# Assistant: LLM chat with tool use
# ---------------------------------------------------------------------------


@app.post("/assistant/chat", response_model=ChatResponse)
async def assistant_chat(payload: ChatRequest) -> ChatResponse:
    """LLM-powered assistant endpoint.

    Accepts a user message and optional conversation history.
    Uses Claude with platform tools to return a grounded answer.
    """
    if not settings.llm_base_url:
        raise HTTPException(
            status_code=503,
            detail="LLM_BASE_URL is not configured. Set it in python/.env.",
        )
    try:
        reply, updated_history = chat_once(
            payload.message, payload.history, _get_session()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Assistant error: {exc}") from exc
    return ChatResponse(reply=reply, history=updated_history)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def start() -> None:
    uvicorn.run("app.main:app", host=settings.server_host, port=settings.server_port, reload=True)


if __name__ == "__main__":
    start()

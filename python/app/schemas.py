"""Pydantic request/response schemas for all API endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


# -- Data Sources --


class CreateDataSource(BaseModel):
    api_url: str | None = None
    description: str | None = None
    name: str | None = None


class DataSourceResponse(BaseModel):
    source_id: uuid.UUID
    api_url: str | None = None
    description: str | None = None
    is_deleted: bool | None = None
    name: str | None = None


# -- Asset Details --


class CreateAssetDetails(BaseModel):
    asset_id: uuid.UUID | None = None
    asset_class: str | None = None
    description: str | None = None
    region: str | None = None
    source_id: uuid.UUID | None = None
    symbol: str | None = None


class AssetDetailsResponse(BaseModel):
    asset_id: uuid.UUID
    valid_from: datetime
    asset_class: str | None = None
    description: str | None = None
    is_deleted: bool | None = None
    region: str | None = None
    source_id: uuid.UUID | None = None
    symbol: str | None = None


# -- Assets by Class --


class CreateAssetByClass(BaseModel):
    asset_class: str
    asset_id: uuid.UUID | None = None
    description: str | None = None
    region: str | None = None
    symbol: str | None = None


class AssetByClassResponse(BaseModel):
    asset_class: str
    asset_id: uuid.UUID
    description: str | None = None
    region: str | None = None
    symbol: str | None = None


# -- Time Series --


class CreateTimeSeries(BaseModel):
    asset_id: uuid.UUID
    source_id: uuid.UUID
    year_month: date
    event_time: datetime
    metrics: dict[str, float] = {}


class TimeSeriesResponse(BaseModel):
    asset_id: uuid.UUID
    source_id: uuid.UUID
    year_month: date
    event_time: datetime
    metrics: dict[str, float]


# -- Ingestion Pipeline --


class IngestRequest(BaseModel):
    symbol: str
    source_id: uuid.UUID
    interval: str = "1d"
    asset_class: str = "crypto"
    region: str = "global"
    description: str | None = None
    provider: str = "binance"


class IngestResponse(BaseModel):
    asset_id: uuid.UUID
    symbol: str
    fetched: int
    transformed: int
    stored: int
    skipped: int
    failures: int


# -- Analytics --


class AnalyticsRequest(BaseModel):
    asset_id: uuid.UUID
    source_id: uuid.UUID
    metric: str = "close"


class AggregationResponse(BaseModel):
    asset_id: uuid.UUID
    metric: str
    count: int
    min: float
    max: float
    mean: float
    sum: float
    stddev: float


class TrendResponse(BaseModel):
    asset_id: uuid.UUID
    metric: str
    slope: float
    direction: str
    pct_change: float
    start_value: float
    end_value: float


class ForecastRequest(BaseModel):
    asset_id: uuid.UUID
    source_id: uuid.UUID
    metric: str = "close"
    periods: int = 7


class ForecastPoint(BaseModel):
    event_time: str
    predicted_value: float
    period: int


class ForecastResponse(BaseModel):
    asset_id: uuid.UUID
    metric: str
    predictions: list[ForecastPoint]


class RiskResponse(BaseModel):
    asset_id: uuid.UUID
    metric: str
    volatility: float
    max_drawdown_pct: float
    avg_daily_return_pct: float
    sharpe_approx: float


class CompareRequest(BaseModel):
    asset_a_id: uuid.UUID
    asset_a_source_id: uuid.UUID
    asset_b_id: uuid.UUID
    asset_b_source_id: uuid.UUID
    metric: str = "close"


class CompareResponse(BaseModel):
    metric: str
    asset_a: AggregationResponse
    asset_b: AggregationResponse


# -- Export --


class ExportRequest(BaseModel):
    asset_id: uuid.UUID
    source_id: uuid.UUID
    format: str = "jsonl"


# -- Assistant --


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    reply: str
    history: list[dict]

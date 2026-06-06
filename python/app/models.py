"""Domain models mirroring the Cassandra schema and pipeline data structures."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class IngestionStats:
    """Tracks counts across the extract -> transform -> load pipeline."""

    fetched: int = 0
    transformed: int = 0
    stored: int = 0
    skipped: int = 0
    failures: int = 0

    def summary(self) -> str:
        return (
            f"Fetched: {self.fetched} | Transformed: {self.transformed} | "
            f"Stored: {self.stored} | Skipped: {self.skipped} | "
            f"Failures: {self.failures}"
        )


@dataclass
class TimeSeriesRecord:
    """A single time-series data point for the time_series_data table."""

    asset_id: uuid.UUID
    source_id: uuid.UUID
    year_month: date
    event_time: datetime
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class DataSource:
    """Row in the data_sources table."""

    source_id: uuid.UUID
    api_url: str | None = None
    description: str | None = None
    is_deleted: bool | None = None
    name: str | None = None


@dataclass
class AssetDetails:
    """Row in the asset_details table (SCD Type 2)."""

    asset_id: uuid.UUID
    valid_from: datetime
    asset_class: str | None = None
    description: str | None = None
    is_deleted: bool | None = None
    region: str | None = None
    source_id: uuid.UUID | None = None
    symbol: str | None = None


@dataclass
class AssetByClass:
    """Row in the assets_by_class lookup table."""

    asset_class: str
    asset_id: uuid.UUID
    description: str | None = None
    region: str | None = None
    symbol: str | None = None

"""Unit tests for app/models.py domain dataclasses."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from app.models import AssetByClass, AssetDetails, DataSource, IngestionStats, TimeSeriesRecord


# ---------------------------------------------------------------------------
# IngestionStats
# ---------------------------------------------------------------------------

def test_ingestion_stats_defaults():
    stats = IngestionStats()
    assert stats.fetched == 0
    assert stats.transformed == 0
    assert stats.stored == 0
    assert stats.skipped == 0
    assert stats.failures == 0


def test_ingestion_stats_summary_contains_counts():
    stats = IngestionStats(fetched=10, transformed=9, stored=8, skipped=1, failures=0)
    summary = stats.summary()
    assert "10" in summary
    assert "9" in summary
    assert "8" in summary
    assert "1" in summary


def test_ingestion_stats_summary_labels():
    stats = IngestionStats()
    summary = stats.summary()
    assert "Fetched" in summary
    assert "Transformed" in summary
    assert "Stored" in summary
    assert "Skipped" in summary
    assert "Failures" in summary


def test_ingestion_stats_mutability():
    stats = IngestionStats()
    stats.fetched += 5
    stats.failures += 2
    assert stats.fetched == 5
    assert stats.failures == 2


# ---------------------------------------------------------------------------
# TimeSeriesRecord
# ---------------------------------------------------------------------------

def test_time_series_record_fields():
    asset_id = uuid.uuid4()
    source_id = uuid.uuid4()
    ym = date(2024, 1, 1)
    et = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
    metrics = {"close": 42500.0, "volume": 123.45}

    rec = TimeSeriesRecord(
        asset_id=asset_id,
        source_id=source_id,
        year_month=ym,
        event_time=et,
        metrics=metrics,
    )

    assert rec.asset_id == asset_id
    assert rec.source_id == source_id
    assert rec.year_month == ym
    assert rec.event_time == et
    assert rec.metrics["close"] == 42500.0


def test_time_series_record_default_metrics():
    rec = TimeSeriesRecord(
        asset_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        year_month=date(2024, 1, 1),
        event_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    assert rec.metrics == {}


# ---------------------------------------------------------------------------
# DataSource
# ---------------------------------------------------------------------------

def test_data_source_fields():
    sid = uuid.uuid4()
    ds = DataSource(
        source_id=sid,
        api_url="https://api.binance.com",
        description="Binance crypto exchange",
        is_deleted=False,
        name="Binance",
    )
    assert ds.source_id == sid
    assert ds.name == "Binance"
    assert ds.is_deleted is False


def test_data_source_optional_fields_default_none():
    ds = DataSource(source_id=uuid.uuid4())
    assert ds.api_url is None
    assert ds.description is None
    assert ds.is_deleted is None
    assert ds.name is None


# ---------------------------------------------------------------------------
# AssetDetails
# ---------------------------------------------------------------------------

def test_asset_details_fields():
    aid = uuid.uuid4()
    sid = uuid.uuid4()
    vf = datetime(2024, 1, 1, tzinfo=timezone.utc)

    ad = AssetDetails(
        asset_id=aid,
        valid_from=vf,
        asset_class="crypto",
        description="Bitcoin",
        is_deleted=False,
        region="global",
        source_id=sid,
        symbol="BTCUSDT",
    )
    assert ad.asset_id == aid
    assert ad.symbol == "BTCUSDT"
    assert ad.asset_class == "crypto"
    assert ad.is_deleted is False


# ---------------------------------------------------------------------------
# AssetByClass
# ---------------------------------------------------------------------------

def test_asset_by_class_required_fields():
    aid = uuid.uuid4()
    abc = AssetByClass(asset_class="stock", asset_id=aid)
    assert abc.asset_class == "stock"
    assert abc.asset_id == aid
    assert abc.description is None
    assert abc.symbol is None

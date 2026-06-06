"""CLI ingestion pipeline: extract, transform, load."""

from __future__ import annotations

import asyncio
import uuid

from app.extract import Extractor
from app.load import Loader
from app.models import IngestionStats
from app.transform import transform_binance_response


async def run() -> None:
    print("Starting Binance ingestion pipeline...")

    stats = IngestionStats()
    asset_id = uuid.uuid4()
    source_id = uuid.uuid4()

    extractor = Extractor()
    try:
        print("Fetching live BTC/USDT daily data from Binance...")
        raw_data = await extractor.fetch_binance_data("BTCUSDT", "1d")
        records = transform_binance_response(raw_data, asset_id, source_id, stats)

        try:
            loader = Loader.connect()
            await loader.load_time_series(records, stats)
            loader.close()
        except Exception as exc:
            print(f"Could not connect to Cassandra. Skipping load phase. Reason: {exc}")
    finally:
        await extractor.close()

    print("--- Ingestion Run Complete ---")
    print(stats.summary())


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

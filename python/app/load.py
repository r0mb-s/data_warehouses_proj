"""Load transformed records into Cassandra."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from cassandra.cluster import Cluster, Session
from cassandra.query import PreparedStatement

from app.config import settings
from app.models import IngestionStats, TimeSeriesRecord

logger = logging.getLogger(__name__)

MAX_CONCURRENT_INSERTS = 50


class Loader:
    """Manages a Cassandra session and batch-inserts time-series records."""

    def __init__(self, session: Session, insert_stmt: PreparedStatement) -> None:
        self._session = session
        self._insert_stmt = insert_stmt
        self._executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_INSERTS)

    @classmethod
    def connect(
        cls,
        host: str = settings.cassandra_host,
        port: int = settings.cassandra_port,
    ) -> Loader:
        """Connect to the cluster and prepare the insert statement."""
        cluster = Cluster([host], port=port)
        session = cluster.connect()
        insert_stmt = session.prepare(
            f"INSERT INTO {settings.keyspace}.time_series_data "
            "(asset_id, source_id, year_month, event_time, metrics) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        return cls(session=session, insert_stmt=insert_stmt)

    def _execute_insert(self, record: TimeSeriesRecord) -> bool:
        """Execute a single blocking insert. Returns True on success."""
        try:
            self._session.execute(
                self._insert_stmt,
                (record.asset_id, record.source_id, record.year_month,
                 record.event_time, record.metrics),
            )
            return True
        except Exception:
            logger.exception("Failed to insert record for event_time=%s", record.event_time)
            return False

    async def load_time_series(
        self,
        records: list[TimeSeriesRecord],
        stats: IngestionStats,
    ) -> None:
        """Concurrently insert records using a thread pool."""
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(self._executor, partial(self._execute_insert, record))
            for record in records
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if result is True:
                stats.stored += 1
            else:
                stats.failures += 1

    def close(self) -> None:
        self._session.cluster.shutdown()
        self._session.shutdown()
        self._executor.shutdown(wait=False)

"""Data extraction from external APIs."""

from __future__ import annotations

from typing import Any

import httpx


class Extractor:
    """Async HTTP client for fetching market data from external sources."""

    BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
    YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_binance_data(
        self,
        symbol: str,
        interval: str,
    ) -> list[list[Any]]:
        """Fetch kline/candlestick data from the Binance public API.

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``.
            interval: Candle interval, e.g. ``"1d"``, ``"1h"``.

        Returns:
            A list of kline arrays as returned by Binance.

        Raises:
            httpx.HTTPStatusError: If Binance responds with a non-2xx status.
        """
        response = await self._client.get(
            self.BINANCE_KLINES_URL,
            params={"symbol": symbol, "interval": interval},
        )
        response.raise_for_status()
        return response.json()

    async def fetch_yahoo_data(
        self,
        symbol: str,
        interval: str = "1d",
        range_: str = "2y",
    ) -> dict[str, Any]:
        """Fetch OHLCV data from the Yahoo Finance chart API.

        Args:
            symbol: Ticker symbol, e.g. ``"AAPL"``, ``"EURUSD=X"``, ``"GC=F"``.
            interval: Candle interval, e.g. ``"1d"``, ``"1wk"``, ``"1h"``.
            range_: Data range, e.g. ``"1y"``, ``"2y"``, ``"5y"``, ``"max"``.

        Returns:
            Raw JSON dict from the Yahoo Finance v8 chart API.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            ValueError: If the API returns an error payload.
        """
        url = self.YAHOO_CHART_URL.format(symbol=symbol)
        response = await self._client.get(
            url,
            params={"interval": interval, "range": range_},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        data = response.json()
        error = data.get("chart", {}).get("error")
        if error:
            raise ValueError(f"Yahoo Finance error: {error}")
        return data

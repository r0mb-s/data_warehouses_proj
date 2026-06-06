"""LLM-powered assistant using a local llama-server (OpenAI-compatible API).

Can be used as:
  - A CLI REPL:  python -m app.assistant  (or: assistant)
  - A library:   from app.assistant import chat_once(message, history, session)

llama-server must be running at settings.llm_base_url (default http://localhost:8079).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import httpx
from cassandra.cluster import Session

from app import analytics
from app.config import settings

KS = settings.keyspace

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI tool-call format)
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_assets",
            "description": "List all financial assets in the data warehouse. Returns asset_id, symbol, asset_class, region, source_id for each asset.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_sources",
            "description": "List all data sources (providers) registered in the data warehouse. Returns source_id, name, api_url.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_time_series",
            "description": "Fetch OHLCV time-series data for a specific asset and data source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string", "description": "UUID of the asset"},
                    "source_id": {"type": "string", "description": "UUID of the data source"},
                    "metric": {
                        "type": "string",
                        "description": "Metric to highlight: open, high, low, close, volume",
                        "default": "close",
                    },
                },
                "required": ["asset_id", "source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_aggregation",
            "description": "Compute count, min, max, mean, sum, stddev for an asset metric.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "source_id": {"type": "string"},
                    "metric": {"type": "string", "default": "close"},
                },
                "required": ["asset_id", "source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trend",
            "description": "Get the price trend for an asset: direction (up/down/flat), slope, and percent change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "source_id": {"type": "string"},
                    "metric": {"type": "string", "default": "close"},
                },
                "required": ["asset_id", "source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": "Forecast future values for an asset metric using linear extrapolation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "source_id": {"type": "string"},
                    "metric": {"type": "string", "default": "close"},
                    "periods": {"type": "integer", "default": 7, "description": "Number of future periods"},
                },
                "required": ["asset_id", "source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk",
            "description": "Compute risk signals: volatility, max drawdown %, avg daily return %, and Sharpe ratio approximation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "source_id": {"type": "string"},
                    "metric": {"type": "string", "default": "close"},
                },
                "required": ["asset_id", "source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_assets",
            "description": "Side-by-side aggregation comparison of two assets on the same metric.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_a_id": {"type": "string"},
                    "asset_a_source_id": {"type": "string"},
                    "asset_b_id": {"type": "string"},
                    "asset_b_source_id": {"type": "string"},
                    "metric": {"type": "string", "default": "close"},
                },
                "required": ["asset_a_id", "asset_a_source_id", "asset_b_id", "asset_b_source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_asset",
            "description": (
                "Agentic tool: fetch full analytics for an asset (aggregation, trend, risk, 7-period forecast) "
                "and return a comprehensive structured summary in one call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "source_id": {"type": "string"},
                    "metric": {"type": "string", "default": "close"},
                },
                "required": ["asset_id", "source_id"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def _fetch_metric_series(
    session: Session, asset_id: str, source_id: str, metric: str
) -> tuple[list[datetime], list[float]]:
    aid = uuid.UUID(asset_id)
    sid = uuid.UUID(source_id)
    rows = list(
        session.execute(
            f"SELECT event_time, metrics FROM {KS}.time_series_data "
            "WHERE asset_id = %s AND source_id = %s ALLOW FILTERING",
            (aid, sid),
        )
    )
    pairs = [
        (r.event_time, (r.metrics or {}).get(metric))
        for r in rows
        if (r.metrics or {}).get(metric) is not None
    ]
    pairs.sort(key=lambda p: p[0])
    return [p[0] for p in pairs], [p[1] for p in pairs]


def execute_tool(name: str, inputs: dict[str, Any], session: Session) -> Any:
    """Execute a named tool and return a JSON-serialisable result."""
    if name == "list_assets":
        rows = session.execute(
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

    if name == "list_sources":
        rows = session.execute(
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

    if name == "fetch_time_series":
        aid = uuid.UUID(inputs["asset_id"])
        sid = uuid.UUID(inputs["source_id"])
        rows = list(
            session.execute(
                f"SELECT event_time, metrics FROM {KS}.time_series_data "
                "WHERE asset_id = %s AND source_id = %s ALLOW FILTERING",
                (aid, sid),
            )
        )
        rows.sort(key=lambda r: r.event_time)
        return [
            {"event_time": r.event_time.isoformat(), **(r.metrics or {})}
            for r in rows
        ]

    if name == "get_aggregation":
        _, values = _fetch_metric_series(
            session, inputs["asset_id"], inputs["source_id"], inputs.get("metric", "close")
        )
        if not values:
            return {"error": "No data found"}
        return analytics.aggregate(values)

    if name == "get_trend":
        timestamps, values = _fetch_metric_series(
            session, inputs["asset_id"], inputs["source_id"], inputs.get("metric", "close")
        )
        if len(values) < 2:
            return {"error": "Not enough data for trend analysis"}
        return analytics.compute_trend(timestamps, values)

    if name == "get_forecast":
        timestamps, values = _fetch_metric_series(
            session, inputs["asset_id"], inputs["source_id"], inputs.get("metric", "close")
        )
        if len(values) < 2:
            return {"error": "Not enough data for forecasting"}
        return analytics.forecast(timestamps, values, periods=inputs.get("periods", 7))

    if name == "get_risk":
        _, values = _fetch_metric_series(
            session, inputs["asset_id"], inputs["source_id"], inputs.get("metric", "close")
        )
        if len(values) < 2:
            return {"error": "Not enough data for risk analysis"}
        return analytics.compute_risk(values)

    if name == "compare_assets":
        _, values_a = _fetch_metric_series(
            session, inputs["asset_a_id"], inputs["asset_a_source_id"], inputs.get("metric", "close")
        )
        _, values_b = _fetch_metric_series(
            session, inputs["asset_b_id"], inputs["asset_b_source_id"], inputs.get("metric", "close")
        )
        if not values_a or not values_b:
            return {"error": "No data for one or both assets"}
        return {
            "metric": inputs.get("metric", "close"),
            "asset_a": {"asset_id": inputs["asset_a_id"], **analytics.aggregate(values_a)},
            "asset_b": {"asset_id": inputs["asset_b_id"], **analytics.aggregate(values_b)},
        }

    if name == "summarize_asset":
        metric = inputs.get("metric", "close")
        timestamps, values = _fetch_metric_series(
            session, inputs["asset_id"], inputs["source_id"], metric
        )
        if len(values) < 2:
            return {"error": "Not enough data to summarize this asset"}
        agg = analytics.aggregate(values)
        trend = analytics.compute_trend(timestamps, values)
        risk = analytics.compute_risk(values)
        forecast = analytics.forecast(timestamps, values, periods=7)
        rows = list(
            session.execute(
                f"SELECT symbol, asset_class, region FROM {KS}.asset_details "
                "WHERE asset_id = %s LIMIT 1",
                (uuid.UUID(inputs["asset_id"]),),
            )
        )
        symbol = rows[0].symbol if rows else "unknown"
        return {
            "asset_id": inputs["asset_id"],
            "symbol": symbol,
            "metric": metric,
            "data_points": agg["count"],
            "aggregation": agg,
            "trend": trend,
            "risk": risk,
            "forecast_next_7_periods": forecast,
        }

    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Agentic chat loop (OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a financial data analyst assistant for a data warehouse platform. "
    "You have access to tools that query the warehouse directly. "
    "Always use the available tools to ground your answers in real data — never guess or hallucinate numbers. "
    "When asked about an asset, first call list_assets to find its IDs, then fetch the relevant analytics. "
    "Be concise and precise. Format numbers clearly."
)


def chat_once(
    user_message: str,
    history: list[dict],
    session: Session,
) -> tuple[str, list[dict]]:
    """Run one user turn through the agentic loop.

    Returns (assistant_reply_text, updated_history).
    history is a list of OpenAI-style message dicts (role/content).
    """
    messages: list[dict] = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    with httpx.Client(base_url=settings.llm_base_url, timeout=120.0) as client:
        while True:
            payload = {
                "model": settings.llm_model,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
            }
            resp = client.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]
            msg = choice["message"]
            messages.append(msg)

            finish_reason = choice.get("finish_reason", "stop")

            if finish_reason == "tool_calls":
                tool_calls = msg.get("tool_calls") or []
                for tc in tool_calls:
                    fn = tc["function"]
                    try:
                        inputs = json.loads(fn["arguments"])
                    except json.JSONDecodeError:
                        inputs = {}
                    result = execute_tool(fn["name"], inputs, session)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, default=str),
                    })
                continue

            # stop / end_turn / any other reason — return text
            reply = msg.get("content") or "(no response)"
            # Strip the system message from returned history
            returned_history = [m for m in messages if m.get("role") != "system"]
            return reply, returned_history


# ---------------------------------------------------------------------------
# CLI REPL
# ---------------------------------------------------------------------------


def main() -> None:
    from cassandra.cluster import Cluster

    print("Data Warehouse Assistant (type 'quit' to exit)")
    print(f"LLM: {settings.llm_base_url}  model={settings.llm_model}\n")

    cluster = Cluster([settings.cassandra_host], port=settings.cassandra_port)
    db_session = cluster.connect()
    history: list[dict] = []

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break
            if user_input.lower() in {"quit", "exit", "q"}:
                print("Bye!")
                break
            if not user_input:
                continue
            try:
                reply, history = chat_once(user_input, history, db_session)
                print(f"\nAssistant: {reply}\n")
            except Exception as exc:
                print(f"Error: {exc}\n")
    finally:
        db_session.shutdown()
        cluster.shutdown()


if __name__ == "__main__":
    main()

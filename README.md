# Data Warehouse Platform

A full-stack financial data warehouse that ingests market data from **Binance** (crypto) and **Yahoo Finance** (stocks, forex, ETFs, commodities), stores it in **Apache Cassandra**, and provides analytics, forecasting, risk analysis, Spark-compatible export, and an LLM-powered assistant via MCP.

---

## Architecture Overview

```
cassandra-frontend/   React + Vite frontend        → http://localhost:5173
python/               FastAPI backend               → http://localhost:8083
                      Cassandra                     → localhost:9042
                      llama-server (local LLM)      → http://localhost:8079
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | >= 3.11 |
| Node.js | >= 18 |
| Apache Cassandra | >= 4.0 |
| llama-server (llama.cpp) | any recent build |

---

## 1. Cassandra Setup

### Start Cassandra

```bash
sudo systemctl start cassandra
# or wherever your Cassandra install is
```

### Create keyspace and tables

Open `cqlsh` and run:

```sql
CREATE KEYSPACE IF NOT EXISTS datawarehousesproject
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE datawarehousesproject;

CREATE TABLE IF NOT EXISTS data_sources (
    source_id   UUID PRIMARY KEY,
    api_url     TEXT,
    description TEXT,
    is_deleted  BOOLEAN,
    name        TEXT
);

CREATE TABLE IF NOT EXISTS asset_details (
    asset_id    UUID,
    valid_from  TIMESTAMP,
    asset_class TEXT,
    description TEXT,
    is_deleted  BOOLEAN,
    region      TEXT,
    source_id   UUID,
    symbol      TEXT,
    PRIMARY KEY (asset_id, valid_from)
) WITH CLUSTERING ORDER BY (valid_from DESC);

CREATE TABLE IF NOT EXISTS assets_by_class (
    asset_class TEXT,
    asset_id    UUID,
    description TEXT,
    region      TEXT,
    symbol      TEXT,
    PRIMARY KEY (asset_class, asset_id)
);

CREATE TABLE IF NOT EXISTS time_series_data (
    asset_id    UUID,
    source_id   UUID,
    year_month  DATE,
    event_time  TIMESTAMP,
    metrics     MAP<TEXT, DOUBLE>,
    PRIMARY KEY ((asset_id, source_id, year_month), event_time)
) WITH CLUSTERING ORDER BY (event_time DESC);
```

---

## 2. Backend Setup

### Folder

```
proj/python/
```

### Create and activate virtual environment

```bash
cd python/
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
```

### Install Python packages

```bash
pip install -e .
```

This installs all dependencies from `pyproject.toml`:

| Package | Version |
|---|---|
| fastapi | >= 0.115.0 |
| uvicorn[standard] | >= 0.30.0 |
| cassandra-driver | >= 3.29.0 |
| httpx | >= 0.27.0 |
| pydantic | >= 2.9.0 |
| pydantic-settings | >= 2.5.0 |
| python-dotenv | >= 1.0.0 |
| mcp | >= 1.0.0 |

### Configure environment

Create `python/.env`:

```env
CASSANDRA_HOST=127.0.0.1
CASSANDRA_PORT=9042
SERVER_HOST=0.0.0.0
SERVER_PORT=8083
LLM_BASE_URL=http://localhost:8079
LLM_MODEL=local
```

### Start the API server

```bash
cd python/
source .venv/bin/activate
python -m app.main
# or use the console script:
serve
```

Server starts at **http://localhost:8083** with hot-reload enabled.

### Available console scripts (from `python/`)

| Command | What it does |
|---|---|
| `serve` | Start the FastAPI server |
| `fill` | Run the CLI ingestion pipeline (fetches BTC/USDT from Binance) |
| `mcp-serve` | Start the MCP server (stdio transport, for Claude Desktop / Claude Code) |
| `assistant` | Start the CLI REPL assistant |

---

## 3. Frontend Setup

### Folder

```
proj/cassandra-frontend/
```

### Install Node packages

```bash
cd cassandra-frontend/
npm install
```

### Start the dev server

```bash
npm run dev
```

Frontend starts at **http://localhost:5173**.  
All `/api/*` requests are proxied to `http://localhost:8083` automatically.

---

## 5. Port Reference

| Service | Port | Notes |
|---|---|---|
| FastAPI backend | **8083** | REST API |
| React frontend | **5173** | Vite dev server |
| Cassandra | **9042** | CQL native transport |
| llama-server | **8079** | OpenAI-compatible LLM API |

---

## 6. Database Schema

**Keyspace:** `datawarehousesproject`

### `data_sources`
Registry of data providers.

| Column | Type | Notes |
|---|---|---|
| `source_id` | UUID | Primary key |
| `name` | TEXT | e.g. "Binance" |
| `api_url` | TEXT | e.g. "https://api.binance.com" |
| `description` | TEXT | |
| `is_deleted` | BOOLEAN | Soft-delete flag |

### `asset_details`
SCD Type 2 asset metadata — changes are stored as new versions, never overwritten.

| Column | Type | Notes |
|---|---|---|
| `asset_id` | UUID | Partition key |
| `valid_from` | TIMESTAMP | Clustering key DESC — newest version first |
| `symbol` | TEXT | e.g. "BTCUSDT", "AAPL" |
| `asset_class` | TEXT | e.g. "crypto", "stock" |
| `region` | TEXT | e.g. "global", "US", "DE" |
| `description` | TEXT | |
| `source_id` | UUID | Which provider this came from |
| `is_deleted` | BOOLEAN | Soft-delete — set by inserting a new version with `is_deleted=True` |

### `assets_by_class`
Lookup table for filtering assets by class.

| Column | Type | Notes |
|---|---|---|
| `asset_class` | TEXT | Partition key |
| `asset_id` | UUID | Clustering key |
| `symbol` | TEXT | |
| `region` | TEXT | |
| `description` | TEXT | |

### `time_series_data`
OHLCV candlestick data. Partitioned by asset + source + month.

| Column | Type | Notes |
|---|---|---|
| `asset_id` | UUID | Partition key (composite) |
| `source_id` | UUID | Partition key (composite) |
| `year_month` | DATE | Partition key (composite) — prevents unbounded partitions |
| `event_time` | TIMESTAMP | Clustering key DESC |
| `metrics` | MAP<TEXT, DOUBLE> | Keys: `open`, `high`, `low`, `close`, `volume` |

---

## 7. API Endpoints Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/sources` | List all data sources |
| `GET` | `/sources/{source_id}` | Get data source by ID |
| `POST` | `/sources` | Create a data source |
| `DELETE` | `/sources/{source_id}` | Soft-delete a data source |
| `GET` | `/assets` | List all asset versions |
| `GET` | `/assets/{asset_id}` | All SCD versions of an asset. Add `?as_of=<ISO8601>` for point-in-time query |
| `POST` | `/assets` | Create an asset record |
| `DELETE` | `/assets/{asset_id}` | Soft-delete asset (inserts new SCD version with `is_deleted=True`) |
| `GET` | `/assets-by-class` | List assets grouped by class |
| `POST` | `/assets-by-class` | Create asset-by-class entry |
| `GET` | `/time-series` | List time-series. Filter with `?asset_id=&source_id=` |
| `POST` | `/time-series` | Insert a single time-series point |
| `POST` | `/ingest` | Run full ETL pipeline (Binance or Yahoo Finance) |
| `POST` | `/analytics/aggregate` | count / min / max / mean / sum / stddev |
| `POST` | `/analytics/trend` | Linear regression slope, direction, % change |
| `POST` | `/analytics/forecast` | Linear extrapolation for N periods |
| `POST` | `/analytics/risk` | Volatility, max drawdown, Sharpe ratio |
| `POST` | `/analytics/compare` | Side-by-side aggregation of two assets |
| `POST` | `/export` | Download time-series as JSONL or CSV (Spark-ready) |
| `POST` | `/assistant/chat` | LLM-powered chat with warehouse tools |

Interactive API docs: **http://localhost:8083/docs**

---

## 8. Data Providers

### Binance (crypto)

| Field | Value |
|---|---|
| provider | `"binance"` |
| Example symbols | `BTCUSDT`, `ETHUSDT`, `BNBUSDT` |
| Intervals | `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, `1w`, `1M` |
| API key required | No |

### Yahoo Finance (stocks, forex, ETFs, commodities)

| Field | Value |
|---|---|
| provider | `"yahoo"` |
| Example symbols | `AAPL`, `SAP.DE`, `EURUSD=X`, `GC=F` (Gold), `AMS.MC` |
| Intervals | `1d`, `1wk`, `1mo`, `1h`, `5m` |
| API key required | No |

---

## 9. Quick Start (full stack)

```bash
# Terminal 1 — Cassandra (must already be running)
cqlsh
> USE datawarehousesproject;   -- verify keyspace exists

# Terminal 2 — Backend
cd python/
source .venv/bin/activate
serve

# Terminal 3 — Frontend
cd cassandra-frontend/
npm run dev

# Terminal 4 — LLM (optional, needed for assistant tab)
llama-server --port 8079 ...
```

Then open **http://localhost:5173** in your browser.

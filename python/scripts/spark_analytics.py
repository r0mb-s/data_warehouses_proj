"""Spark analytics pipeline for the data warehouse.

Reads time-series data exported from the warehouse (JSONL or CSV), runs a
PySpark aggregation workflow and a Spark MLlib LinearRegression forecasting
workflow, then persists both results back to disk.

Usage
-----
    # Against a real export produced by POST /export:
    python scripts/spark_analytics.py path/to/export.jsonl
    python scripts/spark_analytics.py path/to/export.csv

    # Self-contained demo (generates synthetic BTC-like data internally):
    python scripts/spark_analytics.py

Output directories (created next to the input file, or in spark_output/ when
using the built-in demo data):
    spark_output/aggregations/   – per-asset aggregation stats (CSV)
    spark_output/forecasts/      – linear regression predictions (CSV)

Note: Requires Java 8, 11, or 17 (PySpark is not compatible with Java 21+).
If your default java is newer, set JAVA_HOME before running:
    JAVA_HOME=/usr/lib/jvm/java-11-sapmachine python scripts/spark_analytics.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Auto-detect a compatible JVM (Java 8/11/17) when JAVA_HOME is not set
# ---------------------------------------------------------------------------

def _find_compatible_java() -> str | None:
    """Return path to a Java 8/11/17 home directory, or None if not found."""
    candidates = [
        "/usr/lib/jvm/java-17-openjdk",
        "/usr/lib/jvm/java-17-sapmachine",
        "/usr/lib/jvm/java-11-openjdk",
        "/usr/lib/jvm/java-11-sapmachine",
        "/usr/lib/jvm/java-11-sapmachine-jdk",
        "/usr/lib/jvm/java-8-openjdk",
        "/usr/lib/jvm/java-8-sapmachine",
        "/usr/local/opt/openjdk@17",  # macOS homebrew
        "/usr/local/opt/openjdk@11",
    ]
    for path in candidates:
        java_bin = os.path.join(path, "bin", "java")
        if os.path.isfile(java_bin) and os.access(java_bin, os.X_OK):
            return path
    return None


if "JAVA_HOME" not in os.environ:
    _java_home = _find_compatible_java()
    if _java_home:
        os.environ["JAVA_HOME"] = _java_home
        print(f"[spark_analytics] Auto-selected JAVA_HOME={_java_home}")
    else:
        print(
            "[spark_analytics] WARNING: JAVA_HOME is not set and no Java 8/11/17 "
            "installation was found in common paths. PySpark requires Java 8, 11, or 17. "
            "Set JAVA_HOME manually if this fails."
        )

# ---------------------------------------------------------------------------
# PySpark imports
# ---------------------------------------------------------------------------

from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


# ---------------------------------------------------------------------------
# Sample data builder (used when no file is supplied)
# ---------------------------------------------------------------------------

_SAMPLE_SCHEMA = StructType([
    StructField("asset_id", StringType(), False),
    StructField("source_id", StringType(), False),
    StructField("event_time", TimestampType(), False),
    StructField("open", DoubleType(), True),
    StructField("high", DoubleType(), True),
    StructField("low", DoubleType(), True),
    StructField("close", DoubleType(), True),
    StructField("volume", DoubleType(), True),
])


def _build_sample_rows() -> list[tuple]:
    """Generate ~90 days of synthetic daily OHLCV data for two assets."""
    import math
    import random

    random.seed(42)
    rows: list[tuple] = []

    assets = [
        ("aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000001"),
        ("aaaaaaaa-0000-0000-0000-000000000002", "bbbbbbbb-0000-0000-0000-000000000001"),
    ]

    base_prices = [30_000.0, 150.0]

    for (asset_id, source_id), base in zip(assets, base_prices):
        price = base
        t = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for day in range(90):
            change = price * random.uniform(-0.03, 0.035)
            open_ = price
            close = price + change
            high = max(open_, close) * random.uniform(1.001, 1.02)
            low = min(open_, close) * random.uniform(0.98, 0.999)
            volume = random.uniform(1_000, 50_000)
            rows.append((asset_id, source_id, t, open_, high, low, round(close, 4), volume))
            price = close
            t += timedelta(days=1)

    return rows


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _read_dataframe(spark: SparkSession, path: str):
    """Load a warehouse export file into a Spark DataFrame."""
    if path.endswith(".csv"):
        df = spark.read.csv(path, header=True, inferSchema=True)
    else:
        df = spark.read.json(path)

    # Normalise event_time to a proper timestamp if it was read as string
    if dict(df.dtypes).get("event_time") == "string":
        df = df.withColumn("event_time", F.to_timestamp("event_time"))

    # Ensure numeric columns are cast (JSONL may infer them correctly already)
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df = df.withColumn(col, df[col].cast(DoubleType()))

    return df


def _run_aggregation(df, output_dir: str) -> None:
    """Compute per-asset descriptive statistics on the close price (M6)."""
    print("\n=== Aggregation workflow (M6) ===")

    agg_df = df.groupBy("asset_id").agg(
        F.count("close").alias("count"),
        F.min("close").alias("min_close"),
        F.max("close").alias("max_close"),
        F.avg("close").alias("avg_close"),
        F.sum("close").alias("sum_close"),
        F.stddev("close").alias("stddev_close"),
    )

    agg_df.show(truncate=False)

    out = os.path.join(output_dir, "aggregations")
    agg_df.coalesce(1).write.mode("overwrite").option("header", "true").csv(out)
    print(f"Aggregation results written to: {out}/")


def _run_ml_forecast(df, output_dir: str) -> None:
    """Fit a LinearRegression model per asset and forecast 7 future periods (M7)."""
    print("\n=== ML forecast workflow (M7) ===")

    # Convert event_time to epoch seconds (numeric feature for ML)
    df = df.withColumn("epoch", F.unix_timestamp("event_time").cast(LongType()))
    df = df.filter(F.col("close").isNotNull() & F.col("epoch").isNotNull())

    # Assemble features
    assembler = VectorAssembler(inputCols=["epoch"], outputCol="features")
    df = assembler.transform(df)

    asset_ids = [row["asset_id"] for row in df.select("asset_id").distinct().collect()]

    spark = df.sparkSession
    all_forecasts = []

    for asset_id in asset_ids:
        asset_df = df.filter(F.col("asset_id") == asset_id)
        count = asset_df.count()
        if count < 2:
            print(f"  Skipping {asset_id}: insufficient data ({count} rows)")
            continue

        lr = LinearRegression(featuresCol="features", labelCol="close", maxIter=100)
        model = lr.fit(asset_df)

        coef = model.coefficients[0]
        intercept = model.intercept
        rmse = model.summary.rootMeanSquaredError
        r2 = model.summary.r2

        print(f"\n  Asset: {asset_id}")
        print(f"    slope={coef:.6f}  intercept={intercept:.4f}  RMSE={rmse:.4f}  R²={r2:.4f}")

        # Auto-detect interval: median gap between consecutive timestamps
        times = sorted(
            row["epoch"]
            for row in asset_df.select("epoch").collect()
        )
        gaps = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        interval = sorted(gaps)[len(gaps) // 2] if gaps else 86400

        last_epoch = times[-1]
        for period in range(1, 8):
            future_epoch = last_epoch + interval * period
            predicted = coef * future_epoch + intercept
            future_dt = datetime.fromtimestamp(future_epoch, tz=timezone.utc).isoformat()
            all_forecasts.append((asset_id, period, future_dt, float(round(predicted, 6))))

    if not all_forecasts:
        print("  No forecasts produced.")
        return

    forecast_schema = StructType([
        StructField("asset_id", StringType(), False),
        StructField("period", LongType(), False),
        StructField("forecast_time", StringType(), False),
        StructField("predicted_close", DoubleType(), False),
    ])
    forecast_df = spark.createDataFrame(all_forecasts, schema=forecast_schema)

    print("\n  Forecast table:")
    forecast_df.show(truncate=False)

    out = os.path.join(output_dir, "forecasts")
    forecast_df.coalesce(1).write.mode("overwrite").option("header", "true").csv(out)
    print(f"Forecast results written to: {out}/")


def main() -> None:
    # Java 17+ requires explicit module access for Spark's unsafe memory layer.
    _java_opts = (
        "--add-opens=java.base/java.lang=ALL-UNNAMED "
        "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED "
        "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED "
        "--add-opens=java.base/java.io=ALL-UNNAMED "
        "--add-opens=java.base/java.net=ALL-UNNAMED "
        "--add-opens=java.base/java.nio=ALL-UNNAMED "
        "--add-opens=java.base/java.util=ALL-UNNAMED "
        "--add-opens=java.base/java.util.concurrent=ALL-UNNAMED "
        "--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED "
        "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED "
        "--add-opens=java.base/sun.nio.cs=ALL-UNNAMED "
        "--add-opens=java.base/sun.security.action=ALL-UNNAMED "
        "--add-opens=java.base/sun.util.calendar=ALL-UNNAMED "
        "--add-opens=java.security.jgss/sun.security.krb5=ALL-UNNAMED "
    )
    spark = SparkSession.builder \
        .appName("DataWarehouse-Analytics") \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.driver.extraJavaOptions", _java_opts) \
        .config("spark.executor.extraJavaOptions", _java_opts) \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "spark_output")
        print(f"Reading from file: {input_path}")
        df = _read_dataframe(spark, input_path)
    else:
        print("No input file provided — using built-in synthetic data.")
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "spark_output",
        )
        df = spark.createDataFrame(_build_sample_rows(), schema=_SAMPLE_SCHEMA)

    df.cache()
    print(f"\nLoaded {df.count()} rows across {df.select('asset_id').distinct().count()} asset(s).")
    df.printSchema()

    _run_aggregation(df, output_dir)
    _run_ml_forecast(df, output_dir)

    spark.stop()
    print("\nDone.")


if __name__ == "__main__":
    main()

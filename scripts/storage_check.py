"""Compare identical aggregate SQL after loading; document scope and equivalence."""

import json
import sqlite3
from pathlib import Path
from time import perf_counter
import duckdb
import numpy as np
import pandas as pd


def main():
    out = Path(__file__).resolve().parents[1] / "reports"
    path = out / "product_monthly.parquet"
    frame = pd.read_parquet(path)
    query = (
        "SELECT Product, month, SUM(count) AS n FROM counts GROUP BY Product, month ORDER BY Product, month"
    )
    with sqlite3.connect(":memory:") as sql, duckdb.connect() as duck:
        frame.to_sql("counts", sql, index=False)
        duck.from_parquet(str(path)).create_view("counts")
        timings = {}
        observations = []
        for name, conn in [("sqlite_memory", sql), ("duckdb_parquet", duck)]:
            times = []
            for _ in range(7):
                start = perf_counter()
                data = conn.execute(query).fetchall()
                times.append(perf_counter() - start)
            timings[name] = float(np.median(times))
            observations.append(data)
        if observations[0] != observations[1]:
            raise ValueError("Aggregate mismatch")
    (out / "storage_benchmark.json").write_text(
        json.dumps(
            {
                "median_seconds": timings,
                "repetitions": len(times),
                "rows": len(data),
                "note": "Warm group-by latency, excludes ingestion and setup. Retain SQLite for legacy warehouse; the viewer reads Parquet directly and needs no DB migration.",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

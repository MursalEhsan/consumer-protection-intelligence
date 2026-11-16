"""Stream a CFPB snapshot into monthly counts with no individual records."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def aggregate(source: Path, target: Path, as_of: str) -> None:
    cutoff = pd.Timestamp(as_of).normalize() - pd.Timedelta(days=15)
    fields = ["Date received", "Product", "Issue"]
    groups = []
    for chunk in pd.read_csv(source, usecols=fields, dtype=str, chunksize=200000):
        dates = pd.to_datetime(chunk.pop("Date received"), errors="raise")
        if dates.isna().any() or dates.max() > pd.Timestamp(as_of):
            raise ValueError("Invalid received date for snapshot")
        chunk["month"] = dates.dt.to_period("M")
        chunk = chunk[chunk.month.dt.end_time.dt.normalize() <= cutoff]
        groups.append(chunk.fillna("(unspecified)").value_counts(sort=False))
    counts = (
        pd.concat(groups).groupby(level=["Product", "Issue", "month"]).sum().rename("count").reset_index()
    )
    counts["month"] = counts.month.astype(str)
    counts["product_total"] = counts.groupby(["Product", "month"])["count"].transform("sum")
    counts["share"] = counts["count"] / counts.product_total
    target.parent.mkdir(parents=True, exist_ok=True)
    counts.to_parquet(target, index=False)
    with source.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    target.with_suffix(".json").write_text(
        json.dumps(
            {
                "source_sha256": digest,
                "as_of": as_of,
                "rows_in_mature_months": int(counts["count"].sum()),
                "last_month": counts.month.max(),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    aggregate(args.source, args.target, args.as_of)

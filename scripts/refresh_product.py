"""Refresh product counts, replay, and analyst queue from the dated local snapshot."""

import json
import pandas as pd
from product_counts import aggregate
from detector import ROOT, replay
from backtest import main as backtest


def main() -> None:
    meta = json.loads((ROOT / "output/cfpb_source_sample.json").read_text())
    target = ROOT / "reports/product_monthly.parquet"
    aggregate(ROOT / "output/complaints.csv.zip", target, meta["retrieval_timestamp_utc"][:10])
    actual = json.loads(target.with_suffix(".json").read_text())["source_sha256"]
    if actual != meta["source_sha256"]:
        raise ValueError("Input snapshot changed during refresh")
    replay(pd.read_parquet(target)).to_parquet(ROOT / "reports/detector_replay.parquet", index=False)
    backtest()


if __name__ == "__main__":
    main()

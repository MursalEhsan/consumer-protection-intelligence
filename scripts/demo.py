"""Run the two smoke paths and export their synthetic review queue."""

from pathlib import Path
import pandas as pd
from detector import ROOT, replay
from fixture_model import main as smoke_classifier


def main() -> None:
    smoke_classifier()
    results = replay(pd.read_parquet(ROOT / "tests/fixtures/monthly.parquet"))
    target = Path("output/demo")
    target.mkdir(parents=True, exist_ok=True)
    results.to_parquet(target / "scores.parquet", index=False)
    flags = results[results.glm]
    if flags.empty:
        raise AssertionError("Expected synthetic spike was missed")
    flags.to_csv(target / "watchlist.csv", index=False)
    flags.to_parquet(target / "watchlist.parquet", index=False)
    print("Synthetic fixture pipeline passed.")


if __name__ == "__main__":
    main()

"""Run the two smoke paths and export their synthetic review queue."""

from pathlib import Path
import numpy as np
from clusters import track, TEXT
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
    words = pd.read_parquet(ROOT / "tests/fixtures/synthetic_embeddings.parquet").rename(
        columns={"synthetic_text": TEXT}
    )
    vectors = np.stack(words.pop("embedding"))
    groups = track(words, vectors)
    if groups.empty:
        raise AssertionError("Synthetic cluster smoke produced no clusters")
    groups.to_csv(target / "clusters.csv", index=False)
    print("Synthetic fixture pipeline passed.")


if __name__ == "__main__":
    main()

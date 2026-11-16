"""Generate synthetic product/month strata for installation and SQL smoke checks."""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def generate() -> pd.DataFrame:
    rows = []
    for i, month in enumerate(pd.period_range("2019-01", periods=60, freq="M")):
        for p in ["Demo current account", "Demo credit"]:
            for issue, count in [
                ("Demo billing", 10 + i % 12),
                ("Demo access", 190 if i >= 58 else 15 + i % 4),
            ]:
                rows.append((str(month), p, issue, count))
    frame = pd.DataFrame(rows, columns=["month", "Product", "Issue", "count"])
    return frame


if __name__ == "__main__":
    out = ROOT / "tests/fixtures/monthly.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    generate().to_parquet(out, index=False)

"""Freeze observed coverage boundaries separately from proposed equivalences."""

import pandas as pd
from detector import ROOT


def inventory(frame: pd.DataFrame) -> pd.DataFrame:
    end = frame.month.max()
    result = []
    for (p, i), g in frame.groupby(["Product", "Issue"]):
        first, last = g.month.min(), g.month.max()
        absent = pd.period_range(first, last, freq="M").astype(str).difference(g.month)
        result.append(
            (
                p,
                i,
                first,
                last,
                " ".join(absent),
                "still observed" if last == end else "disappeared; cause unverified",
            )
        )
    return pd.DataFrame(
        result, columns=["product", "issue", "first", "last", "interior_absent_months", "status"]
    )


if __name__ == "__main__":
    inventory(pd.read_parquet(ROOT / "reports/product_monthly.parquet")).to_csv(
        ROOT / "reports/taxonomy_coverage.csv", index=False
    )

"""Evaluate predeclared event windows and export the review queue."""

import numpy as np
import pandas as pd
from detector import ROOT, CFG
from cfpb_pipeline import find_emerging_issue_candidates


def legacy_source(raw):
    overall = (
        raw.groupby(["month", "Issue"])["count"]
        .sum()
        .reset_index()
        .rename(columns={"month": "complaint_month", "Issue": "issue", "count": "complaint_count"})
    )
    overall["monthly_denominator"] = overall.groupby("complaint_month").complaint_count.transform("sum")
    overall["complaint_share"] = overall.complaint_count / overall.monthly_denominator
    return overall


def main():
    out = ROOT / "reports"
    df = pd.read_parquet(out / "detector_replay.parquet")
    raw = pd.read_parquet(out / "product_monthly.parquet")
    legacy = find_emerging_issue_candidates(legacy_source(raw), raw.month.max()).rename(
        columns={"complaint_month": "month"}
    )
    legacy = legacy[legacy.month >= CFG["start"]].reset_index(drop=True)
    events = pd.read_csv(ROOT / "docs/backtest_events.csv")
    rows = []
    details = []
    for method in ["legacy", "rolling_z", "ewma", "glm"]:
        f = legacy if method == "legacy" else df[df[method]]
        matched = set()
        delays = []
        for event in events.itertuples():
            m = pd.Period(event.event_date, freq="M")
            delta = f.month.map(lambda s: pd.Period(s, "M").ordinal - m.ordinal)
            mask = f.issue.eq(event.issue) & delta.between(0, CFG["event_lag_months"])
            if method != "legacy":
                mask &= f["product"].eq(event.product)
            matched.update(f.index[mask])
            delay = delta[mask].min()
            details.append((method, event.source_url, event.event_date, event.product, event.issue, delay))
            if pd.notna(delay):
                delays.append(delay)
        months = len(pd.period_range(CFG["start"], raw.month.max(), freq="M"))
        rows.append(
            (
                method,
                len(delays),
                len(events),
                len(delays) / len(events),
                np.median(delays) if delays else None,
                (len(f) - len(matched)) * 12 / months,
                len(f),
            )
        )
    cols = [
        "method",
        "matched_events",
        "events",
        "recall",
        "median_delay_months",
        "unmatched_alerts_per_year",
        "alerts",
    ]
    table = pd.DataFrame(rows, columns=cols).set_index("method")
    table.to_csv(out / "backtest_table.csv")
    pd.DataFrame(details, columns=["method", "source", "date", "product", "issue", "delay_months"]).to_csv(
        out / "event_results.csv", index=False
    )
    better = (
        table.loc["glm", "recall"] > table.loc["legacy", "recall"]
        and table.loc["glm", "unmatched_alerts_per_year"] <= table.loc["legacy", "unmatched_alerts_per_year"]
    )
    method = "glm" if better else "legacy"
    if better:
        watch = df[df.glm & df.month.eq(raw.month.max())].copy()
        watch["severity"] = watch["count"] / watch.expected
        watch["confidence"] = "BH-adjusted count-model tail; exploratory"
    else:
        watch = legacy[legacy.month.eq(raw.month.max())].copy()
        watch["product"] = "All products"
        watch["severity"] = watch.seasonal_z_score
        watch["confidence"] = "Unvalidated seasonal screen"
    watch["method"] = method
    watch.to_csv(out / "watchlist.csv", index=False)
    watch.to_parquet(out / "watchlist.parquet", index=False)
    (out / "backtest.md").write_text(
        "# Historical event alignment\n\n"
        + table.to_markdown()
        + "\n\nRetained method: "
        + method
        + ". Matched date is measured from the public action, not incident onset. Legacy tests all-product labels and has broader match eligibility. Zero-history product series and taxonomy changes can reduce GLM coverage. Overlapping action windows are dependent. Unmatched alerts per year is a workload proxy. A census of false alarms is unavailable.\n\n[Event-by-event results](event_results.csv) · [Event register](../docs/backtest_events.csv) · [Aggregate snapshot](product_monthly.json).\n"
    )


if __name__ == "__main__":
    main()

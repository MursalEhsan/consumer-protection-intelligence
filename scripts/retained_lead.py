"""Compare narrative matches with the retained all-product watchlist."""

import json
import numpy as np
import pandas as pd
from backtest import legacy_source
from cfpb_pipeline import find_emerging_issue_candidates
from detector import ROOT


def main() -> None:
    out = ROOT / "reports"
    raw = pd.read_parquet(out / "product_monthly.parquet")
    flags = find_emerging_issue_candidates(legacy_source(raw), raw.month.max())
    d = pd.read_csv(out / "cluster_event_matches.csv")
    delays = []
    for e in d.itertuples():
        months = flags.loc[flags.issue == e.issue, "complaint_month"]
        offsets = months.map(lambda s: pd.Period(s, "M").ordinal - pd.Period(e.date, "M").ordinal)
        delays.append(offsets[offsets.between(-2, 2)].min())
    d["legacy_delay"] = delays
    d["restricted_lead_vs_retained"] = d.legacy_delay.fillna(3) - d.cluster_delay.fillna(3)
    d.to_csv(out / "lead_vs_retained.csv", index=False)
    cohorts = [g.restricted_lead_vs_retained.to_numpy() for _, g in d.groupby(d.date.str[:7])]
    rng = np.random.default_rng(427)
    boots = [
        np.concatenate([cohorts[i] for i in rng.integers(len(cohorts), size=len(cohorts))]).mean()
        for _ in range(1000)
    ]
    result = {
        "mean": d.restricted_lead_vs_retained.mean(),
        "interval": np.quantile(boots, [0.025, 0.975]).tolist(),
        "earlier": int((d.restricted_lead_vs_retained > 0).sum()),
        "later": int((d.restricted_lead_vs_retained < 0).sum()),
        "both_missed": int((d.cluster_delay.isna() & d.legacy_delay.isna()).sum()),
    }
    (out / "lead_vs_retained.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

"""Evaluate paired alert times with all misses retained in a bounded horizon."""

import json
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from detector import ROOT


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config/clusters.yaml").read_text())
    out = ROOT / "reports"
    clusters = pd.read_csv(out / "clusters.csv")
    alerts = clusters[clusters.new | clusters.growth]
    d = pd.read_parquet(out / "detector_replay.parquet")
    events = pd.read_csv(ROOT / "docs/backtest_events.csv")
    rows = []
    lo = -cfg["event_window_before_months"]
    hi = cfg["event_window_after_months"]
    for row in events.itertuples():
        m = pd.Period(row.event_date, "M").ordinal

        def first(frame, label):
            g = frame[(frame["product"] == row.product) & (frame[label] == row.issue)]
            delta = g.month.map(lambda t: pd.Period(t, "M").ordinal - m)
            return delta[delta.between(lo, hi)].min()

        a = first(alerts, "modal_issue")
        b = first(d[d.glm], "issue")
        rows.append(
            (
                row.event_date,
                row.product,
                row.issue,
                row.source_url,
                a,
                b,
                (hi + 1 if pd.isna(b) else b) - (hi + 1 if pd.isna(a) else a),
            )
        )
    detail = pd.DataFrame(
        rows, columns=["date", "product", "issue", "source", "cluster_delay", "glm_delay", "restricted_lead"]
    )
    detail.to_csv(out / "cluster_event_matches.csv", index=False)
    # Sample calendar event months together because multiple actions can share an alert.
    groups = [g.restricted_lead.to_numpy() for _, g in detail.groupby(detail.date.str[:7])]
    rng = np.random.default_rng(cfg["seed"])
    boots = [
        np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))]).mean()
        for _ in range(1000)
    ]
    stats = {
        "events": len(detail),
        "cluster_matches": int(detail.cluster_delay.notna().sum()),
        "glm_matches": int(detail.glm_delay.notna().sum()),
        "earlier": int((detail.restricted_lead > 0).sum()),
        "later": int((detail.restricted_lead < 0).sum()),
        "both_missed": int((detail.cluster_delay.isna() & detail.glm_delay.isna()).sum()),
        "restricted_mean_months": detail.restricted_lead.mean(),
        "bootstrap_95": np.quantile(boots, [0.025, 0.975]).tolist(),
        "unique_event_months": len(groups),
    }
    (out / "lead_time.json").write_text(json.dumps(stats, indent=2) + "\n")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(range(len(detail)), detail.restricted_lead, color="#42667c")
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set(
        xlabel="Event in register order",
        ylabel="Months earlier (negative = later)",
        title="Narrative alerts versus product GLM, restricted event window",
    )
    fig.tight_layout()
    fig.savefig(out / "cluster_lead.png")
    plt.close(fig)
    cases = [
        "# Historical cases",
        "",
        "Public action dates serve as reference points. A match means category and time overlap. It does not attribute complaints to a named firm.",
    ]
    for i in [0, 14]:
        e = detail.iloc[i]
        p = pd.Period(e.date, "M")
        g = d[
            (d["product"] == e["product"]) & (d.issue == e.issue) & d.month.between(str(p - 12), str(p + 4))
        ]
        raw = pd.read_parquet(out / "product_monthly.parquet")
        actual = raw[
            (raw.Product == e["product"])
            & (raw.Issue == e.issue)
            & raw.month.between(str(p - 12), str(p + 4))
        ]
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(pd.to_datetime(actual.month), actual["count"], label="Published complaints")
        if len(g):
            ax.plot(pd.to_datetime(g.month), g.expected, label="Expected count")
        ax.axvline(p.start_time, color="gray", ls="--", label="Action month")
        ax.legend(fontsize=8)
        ax.set(xlabel="Month received", ylabel="Complaint count", title=e.issue)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(out / f"case_{i}.png")
        plt.close(fig)

        def describe(value):
            return "no matching alert" if pd.isna(value) else f"a match at month offset {int(value)}"

        context = {
            0: "The CFPB filed a proceeding after the bankruptcy of Synapse, a provider connecting fintech platforms to banks. The bankruptcy preceded the filing, so the filing date can miss the original disruption.",
            14: "The Wells Fargo order covered auto-loan servicing, including incorrect payment application and fees. An industry-wide series pools many lenders and can obscure firm-specific changes.",
        }[i]
        cases.extend(
            [
                "",
                f"## {e['product']} | {e.date}",
                "",
                f"{context} The [public action]({e.source}) was mapped in advance to '{e.issue}'. The narrative method produced {describe(e.cluster_delay)}. The product GLM produced {describe(e.glm_delay)}. Sample density, the available product history and the announcement date limit attribution. The data cannot identify the cause of any miss.",
                "",
                f"![Complaint counts around the action](case_{i}.png)",
            ]
        )
    (out / "case_studies.md").write_text("\n".join(cases) + "\n")


if __name__ == "__main__":
    main()

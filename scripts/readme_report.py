"""Render README and associated evidence charts exclusively from committed results."""

import argparse
import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports"


def render(plot: bool = False) -> str:
    def get(name):
        return json.loads((OUT / name).read_text())

    table = pd.read_csv(OUT / "backtest_table.csv").set_index("method")
    old = table.loc["legacy"]
    glm = table.loc["glm"]
    d = get("metrics.json")
    model = d["models"][get("frozen_choices.json")["best"]]
    oracle = d["test_majority_oracle_accuracy"]
    # For this run the training-majority model attained the test-majority constant accuracy.
    base = d["models"]["majority"]
    if base["accuracy"] != oracle:
        raise ValueError("Recalculate retrospective constant macro-F1 for changed run")
    lead = get("lead_vs_retained.json")
    if plot:
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.bar(table.index, table.matched_events, color="#386577")
        ax.set(
            xlabel="Detection method",
            ylabel="Actions matched",
            title="Action windows matched in the retrospective register",
        )
        fig.tight_layout()
        fig.savefig(OUT / "event_recall.png")
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(7, 3))
        y = [base["macro_f1"], model["macro_f1"]]
        ci = [base["bootstrap_95"]["macro_f1"], model["bootstrap_95"]["macro_f1"]]
        ax.bar(["Constant class", "LinearSVC"], y, color=["#8595a1", "#386577"])
        ax.errorbar(
            [0, 1],
            y,
            yerr=[[a - b[0] for a, b in zip(y, ci)], [b[1] - a for a, b in zip(y, ci)]],
            fmt="none",
            color="black",
        )
        ax.set(ylabel="Macro F1", title="Historical narrative classification, row-bootstrap intervals")
        fig.tight_layout()
        fig.savefig(OUT / "macro_f1.png")
        plt.close(fig)
        dates = pd.read_csv(OUT / "lead_vs_retained.csv")
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.bar(range(len(dates)), dates.restricted_lead_vs_retained, color="#386577")
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set(
            xlabel="Event in register order",
            ylabel="Months earlier (negative = later)",
            title="Narrative alerts versus the retained rule, restricted window",
        )
        fig.tight_layout()
        fig.savefig(OUT / "retained_lead.png")
        plt.close(fig)
    return f"""# Consumer Protection Intelligence

A [financial regulator analyst](docs/client_brief.md) uses the [watchlist](reports/watchlist.csv) to choose which changes in published complaint categories to investigate.

[![CI](https://github.com/MursalEhsan/consumer-protection-intelligence/actions/workflows/verify.yml/badge.svg?branch=remediation%2Fevidence-audit)](https://github.com/MursalEhsan/consumer-protection-intelligence/actions/workflows/verify.yml) · [Run the viewer or deploy it](docs/deployment.md) · [Released historical model](config/model_asset.json)

## Which detector earned its place?

The retained seasonal rule matched **{int(old.matched_events)} of {int(old.events)}** public actions, with a median delay of {old.median_delay_months:g} month among matches. The seasonal count model matched {int(glm.matched_events)}. EWMA matched more actions and generated more unmatched alerts. [Backtest and comparison criteria](reports/backtest.md) · [Synthetic spike results](reports/spike_power.csv)

![Actions matched by each method](reports/event_recall.png)

## Did narratives give earlier warning?

The restricted mean advantage over the retained rule was **{lead["mean"]:.2f} months**. The event-month bootstrap interval ranged from {lead["interval"][0]:.2f} to {lead["interval"][1]:.2f} months. Misses count at the end of the observation horizon. [Lead estimates](reports/lead_vs_retained.json) · [All events, including misses](reports/lead_vs_retained.csv) · [Cases](reports/case_studies.md)

![Paired event offsets](reports/retained_lead.png)

## Can complaint text predict its recorded category?

On {d["rows"]:,} held-out historical narratives, LinearSVC achieved **{model["macro_f1"]:.3f} macro-F1** (95% interval {model["bootstrap_95"]["macro_f1"][0]:.3f} to {model["bootstrap_95"]["macro_f1"][1]:.3f}). The constant predictor scored {base["macro_f1"]:.3f} ({base["bootstrap_95"]["macro_f1"][0]:.3f} to {base["bootstrap_95"]["macro_f1"][1]:.3f}). In this run the training and test majorities coincided. [Frozen experiment](reports/classifier_eval.md) · [Metrics and run commit](reports/metrics.json) · [Calibration](reports/reliability.png)

![Macro F1 for the frozen classifier and constant comparator](reports/macro_f1.png)

## Pipeline

```mermaid
flowchart LR
  Bulk[Structured archive] --> Counts[Monthly product and issue counts] --> Replay[Detector replay] --> Watch[Watchlist]
  Archive[Narrative archive] --> Classifier[Frozen classifier] --> Demo[Abstaining demo]
  Archive --> Clusters[Rolling clusters] --> Events[Event comparison]
```

[Structured code](scripts/detector.py) · [Classifier code](scripts/fresh_eval.py) · [Cluster code](scripts/clusters.py)

## Quickstart

Run `make demo` for the synthetic fixture and `make test` for the regression suite. For the viewer, install the [runtime lock](requirements.lock) in a Python 3.12 environment and run `make app`. [Make targets](Makefile) · [Deployment instructions](docs/deployment.md)

## Limitations

- Complaints reflect selective reporting. [Source assessment](docs/CFPB_SOURCE_ASSESSMENT.md)
- Taxonomy harmonization is partial. [Coverage audit](reports/taxonomy_coverage.csv)
- Announcements can follow incidents, and unmatched alerts lack independent adjudication. [Event register](docs/backtest_events.csv)
- Historical archive performance can drift. [Model card](docs/model_card.md)
- Revised monthly data cannot recreate all earlier publication vintages. [Technical report](docs/technical_report.md)

[Client brief](docs/client_brief.md) · [Classifier audit](EVALUATION_AUDIT.md) · [Backtest](reports/backtest.md) · [Remediation log](docs/remediation_log.md)
"""


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    doc = render(not a.check)
    target = ROOT / "README.md"
    if a.check:
        if target.read_text() != doc:
            raise SystemExit("README differs from generated evidence")
    else:
        target.write_text(doc)

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "output"
MANIFEST_PATH = PROJECT_DIR / "CFPB_DATA_MANIFEST.json"
TRENDS_PATH = OUTPUT_DIR / "issue_trends_monthly.csv"
CANDIDATES_PATH = OUTPUT_DIR / "emerging_issue_candidates.csv"
NARRATIVE_METRICS_PATH = OUTPUT_DIR / "cfpb_narrative_model_metrics.json"


def generate() -> None:
    if not MANIFEST_PATH.exists() or not TRENDS_PATH.exists():
        raise FileNotFoundError("Run `make run` first to generate CFPB source and trend outputs.")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    narrative_metrics = (
        json.loads(NARRATIVE_METRICS_PATH.read_text(encoding="utf-8"))
        if NARRATIVE_METRICS_PATH.exists()
        else None
    )
    trends = pd.read_csv(TRENDS_PATH)
    candidates = pd.read_csv(CANDIDATES_PATH) if CANDIDATES_PATH.exists() else pd.DataFrame()
    summary = manifest["dataset_summary"]
    maturity = manifest.get("evaluation_maturity", {})
    latest_month = maturity.get("last_complete_month")

    trends["complaint_month"] = pd.PeriodIndex(trends["complaint_month"], freq="M")
    latest_period = pd.Period(latest_month, freq="M") if latest_month else trends["complaint_month"].max()
    recent_trends = trends[
        trends["complaint_month"].between(latest_period - 11, latest_period)
    ]
    top_issues = (
        recent_trends.groupby("issue", as_index=False)["complaint_count"]
        .sum()
        .sort_values("complaint_count", ascending=False)
        .head(10)
    )
    top_issue_names = top_issues["issue"].tolist()
    chart_data = trends[
        (trends["complaint_month"] >= latest_period - 35)
        & trends["issue"].isin(top_issue_names)
    ].copy()

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(11, 6))
    for issue, group in chart_data.groupby("issue"):
        ax.plot(
            group["complaint_month"].astype(str),
            group["complaint_share"],
            label=issue,
        )
    ax.set_title("Monthly share of CFPB complaints by issue")
    ax.set_xlabel("Complaint month")
    ax.set_ylabel("Share of monthly complaints")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(loc="best", fontsize="small")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "issue_trends.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    missingness = summary.get("missingness_rate_by_field", {})
    missingness_table = "\n".join(
        f"| `{field}` | {rate:.3%} |"
        for field, rate in missingness.items()
        if rate is not None
    ) or "| No full-archive missingness figures available | n/a |"
    top_issue_table = "\n".join(
        f"| {row.issue} | {int(row.complaint_count):,} |"
        for row in top_issues.itertuples(index=False)
    ) or "| No issue counts available | n/a |"
    candidate_table = "\n".join(
        f"| {row.complaint_month} | {row.issue} | {int(row.complaint_count):,} | "
        f"{row.seasonal_z_score if pd.notna(row.seasonal_z_score) else 'n/a'} |"
        for row in candidates.head(10).itertuples(index=False)
    ) or "| None met the exploratory threshold | | |"
    if narrative_metrics is None:
        narrative_section = (
            "The separate official CFPB Narratives Archive model outputs are not present. "
            "Run `make narrative-model` to build the local sample and evaluation.\n"
        )
    else:
        provenance = narrative_metrics["source_provenance"]
        duplicate_checks = provenance["duplicate_leakage_checks"]
        evaluation_rows = []
        for split_name in ("validation", "test"):
            for model_name, result in narrative_metrics["evaluation"][split_name].items():
                evaluation_rows.append(
                    f"| {split_name.title()} | {model_name.replace('_', ' ')} | "
                    f"{result['accuracy']:.4f} | {result['macro_f1']:.4f} | "
                    f"{result['weighted_f1']:.4f} | {result['rows']:,} |"
                )
        evaluation_table = "\n".join(evaluation_rows)
        test_rows = narrative_metrics["evaluation"]["test"]["tfidf_logistic_regression"]["rows"]
        other_rows = narrative_metrics["unseen_issue_label_rows_mapped_to_other"]["test"]
        other_share = other_rows / test_rows
        narrative_section = f"""The separate official CFPB Narratives Archive contained {provenance['source_rows_scanned']:,} rows across selected exports, of which {provenance['narrative_eligible_rows_scanned']:,} met the documented narrative/Issue/date/ID eligibility rule. This selected set is discontinuous; details, missingness, coverage, and yearly taxonomy changes are recorded in `CFPB_NARRATIVE_MODEL_MANIFEST.json`.

The local TF-IDF/logistic-regression baseline uses train dates {provenance['split_periods']['train'][0]}–{provenance['split_periods']['train'][1]}, validation dates {provenance['split_periods']['validation'][0]}–{provenance['split_periods']['validation'][1]}, and a held-out test through {provenance['split_periods']['test'][1]}. The current structured trend snapshot extends through {summary.get('latest_complaint_date')}; those later structured records do not extend text-model coverage.

| Split | Model | Accuracy | Macro-F1 | Weighted-F1 | Rows |
|---|---|---:|---:|---:|---:|
{evaluation_table}

Final-test rows mapped to the heterogeneous Other/out-of-taxonomy class: {other_rows:,} / {test_rows:,} ({other_share:.1%}). Exact duplicate removal removed {duplicate_checks['duplicate_rows_removed']:,} rows; the approximate SimHash check removed {duplicate_checks['near_duplicate_rows_removed']:,} more. Its {duplicate_checks['near_duplicate_oversized_buckets_skipped']} oversized candidate buckets were skipped, so near-duplicate screening is not exhaustive. No human label audit was performed; Issue is an operational source category and model scores are uncalibrated. Do not claim performance on post-{provenance['split_periods']['test'][1]} narratives.
"""

    report = f"""# CFPB Consumer Complaint Data: Source and Trend Case Study

## Executive summary

This project includes a reproducible local pipeline for CFPB complaint-source assessment and current structured-data trend exploration, plus a separate baseline classifier trained on selected official historical narrative exports. The current structured database schema has no narrative field; the narrative archive is a different, discontinuous source with a held-out cutoff of 2026-08-14.

## Source snapshot

| Item | Value |
|---|---|
| Source | [CFPB Consumer Complaint Database]({manifest['source']}) |
| Retrieval timestamp (UTC) | {manifest['retrieval_timestamp_utc']} |
| Archive SHA-256 | `{manifest['snapshot'].get('archive_sha256')}` |
| Rows scanned | {int(summary['row_count']):,} |
| Persisted metadata sample | {int(summary['sample_row_count']):,} rows (maximum 100,000) |
| Complaint date coverage | {summary.get('earliest_complaint_date')} to {summary.get('latest_complaint_date')} |
| Latest complete month used for trends | {latest_month or 'Not calculated'} |
| Narrative columns detected | {', '.join(manifest['narrative_availability'].get('candidate_narrative_columns') or []) or 'None'} |

The sample is selected deterministically from the full archive, capped at 100,000 rows, and stored without complaint IDs. Monthly source aggregates are computed over the full archive, not the sample. The CFPB states that complaints are published after the company responds and confirms a commercial relationship, or after 15 days, whichever comes first, and that complaint data are not representative of all consumer marketplace experiences. The latest received-date-to-retrieval-date gap is not a measured publication lag because record-level publication timestamps are unavailable.

## Historical narrative classifier

{narrative_section}

## Data quality

| Field | Missing in full archive |
|---|---:|
{missingness_table}

Source-level missingness counts are captured in `CFPB_DATA_MANIFEST.json`. The current structured-data sample excludes complaint identifiers and contains no narrative text. The separate archived narrative sample is retained only in ignored local outputs after Complaint ID removal.

## Descriptive issue trends

The following are raw complaint counts over the latest 12 complete months available in this snapshot. They are not prevalence estimates.

| CFPB issue | Complaint count |
|---|---:|
{top_issue_table}

![Monthly share of CFPB complaints by issue](output/issue_trends.png)

## Exploratory candidates

The pipeline flags issue shares that exceed a same-calendar-month historical baseline by at least three sample standard deviations, subject to a minimum monthly count and a minimum of three baseline years. This small, evolving baseline is only a screening heuristic; flagged patterns require analyst review and are not verified incidents.

| Month | Issue | Count | Seasonal z-score |
|---|---|---:|---:|
{candidate_table}

## Reproduction

```bash
make run
make narrative-model
make report
make test
make app
```

The Streamlit dashboard binds to `127.0.0.1`. Each pipeline retrieves only official public CFPB sources when local files are absent; all analysis remains local with no external LLM calls, upload, publication, or deployment.
"""
    (PROJECT_DIR / "CASE_STUDY.md").write_text(report, encoding="utf-8")
    print(f"Wrote report to {PROJECT_DIR / 'CASE_STUDY.md'}")


if __name__ == "__main__":
    generate()

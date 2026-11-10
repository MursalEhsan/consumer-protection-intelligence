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
REPORTS_DIR = PROJECT_DIR / "reports"
PORTFOLIO_REPORT_PATH = REPORTS_DIR / "structured_trends.md"
PORTFOLIO_CHART_PATH = REPORTS_DIR / "issue_trends.png"


def build_trend_chart_data(
    trends: pd.DataFrame,
    last_complete_month: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = trends.copy()
    data["complaint_month"] = pd.PeriodIndex(data["complaint_month"], freq="M")
    latest_period = pd.Period(last_complete_month, freq="M")
    data = data[data["complaint_month"] <= latest_period]
    recent_trends = data[data["complaint_month"].between(latest_period - 11, latest_period)]
    top_issues = (
        recent_trends.groupby("issue", as_index=False)["complaint_count"]
        .sum()
        .sort_values("complaint_count", ascending=False)
        .head(10)
    )
    chart_data = data[
        (data["complaint_month"] >= latest_period - 35)
        & data["issue"].isin(top_issues["issue"])
    ].copy()
    return top_issues, chart_data


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

    latest_period = pd.Period(latest_month, freq="M") if latest_month else trends["complaint_month"].max()
    top_issues, chart_data = build_trend_chart_data(trends, str(latest_period))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
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
    ax.set_title(
        f"Monthly share by issue, through {latest_period} (complete months only)"
    )
    fig.savefig(PORTFOLIO_CHART_PATH, dpi=160, bbox_inches="tight")
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

![Monthly share of CFPB complaints by issue](reports/issue_trends.png)

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

    snapshot_date = summary.get("latest_complaint_date")
    retrieval_date = manifest.get("retrieval_timestamp_utc", "Not recorded")
    candidate_rows = candidates[
        candidates["complaint_month"].astype(str) == str(latest_period)
    ] if not candidates.empty else pd.DataFrame()
    candidate_lines = []
    for row in candidate_rows.itertuples(index=False):
        candidate_lines.append(
            f"| {row.issue} | {int(row.complaint_count):,} | "
            f"{int(row.monthly_denominator):,} | {row.complaint_share:.3%} | "
            f"{row.seasonal_baseline_share:.3%} | {row.baseline_months} |"
        )
    candidate_result = "\n".join(candidate_lines) or (
        "| No issues met the screening rule in the latest complete month | | | | | |"
    )
    most_recent_candidate = (
        candidates.sort_values("complaint_month").iloc[-1]
        if not candidates.empty
        else None
    )
    if most_recent_candidate is None:
        recent_candidate_section = "No issue met the screening rule in the available complete-month trends."
    else:
        candidate_month = str(most_recent_candidate["complaint_month"])
        baseline_months = [
            month.strip()
            for month in str(most_recent_candidate["baseline_months"]).split(",")
            if month.strip()
        ]
        if len(baseline_months) == 5:
            baseline_presence = (
                "The exact candidate label was observed in all five comparison months."
            )
        else:
            baseline_presence = (
                f"The exact candidate label was observed in {len(baseline_months)} "
                "comparison months; absent issue-month rows were not counted as zero."
            )
        candidate_period = pd.Period(candidate_month, freq="M")
        trend_months = pd.PeriodIndex(trends["complaint_month"], freq="M")
        same_month_related = trends[
            (trend_months == candidate_period)
            & trends["issue"].str.contains("investigation", case=False, na=False)
            & (trends["issue"] != most_recent_candidate["issue"])
        ].sort_values("complaint_count", ascending=False)
        related_labels = ", ".join(
            f"`{row.issue}` ({int(row.complaint_count):,})"
            for row in same_month_related.itertuples(index=False)
        )
        label_note = (
            f" Other investigation-labeled categories that month were counted separately: "
            f"{related_labels}."
            if related_labels
            else ""
        )
        recent_candidate_section = (
            f"The most recent earlier flag was **{most_recent_candidate['complaint_month']} — "
            f"{most_recent_candidate['issue']}**: "
            f"{int(most_recent_candidate['complaint_count']):,} of "
            f"{int(most_recent_candidate['monthly_denominator']):,} complaints "
            f"({most_recent_candidate['complaint_share']:.4%}), versus a "
            f"{most_recent_candidate['seasonal_baseline_share']:.4%} mean across "
            f"{most_recent_candidate['baseline_months']}. {baseline_presence}{label_note}"
        )
    top_issue_lines = "\n".join(
        f"| {row.issue} | {int(row.complaint_count):,} |"
        for row in top_issues.head(5).itertuples(index=False)
    )
    structured_report = f"""# CFPB structured complaint trends

**Snapshot received-date coverage through:** {snapshot_date}<br>
**Retrieved:** {retrieval_date}<br>
**Latest complete complaint month under the maturity rule:** {latest_period}

## What the trend shows

The chart below shows monthly shares for the ten highest-count issue labels over the latest 12 complete months, plotted across the latest 36 complete months. Counts and monthly denominators are full-source aggregates over valid complaint dates, not the capped local sample. Shares are each issue's count divided by all complaints with a valid received date in that calendar month.

![Monthly CFPB complaint shares by issue through {latest_period}](issue_trends.png)

The five largest issue counts across the latest 12 complete months were:

| Issue | Complaint count |
|---|---:|
{top_issue_lines}

## Screening result for {latest_period}

The existing exploratory screen requires at least 50 complaints and compares an issue's share with up to five prior **observed** months of the same calendar month. It requires at least three observations and flags a rise of at least three sample standard deviations. This is a prompt for investigation, not a significance test, incident finding, causal result, or evidence of consumer harm.

| Issue | Count | All complaints that month | Observed share | Mean comparison share | Historical months used |
|---|---:|---:|---:|---:|---|
{candidate_result}

{recent_candidate_section}

Missing issue-month rows are not zero-filled by the existing comparison; absent rows may reflect zero recorded counts, while changed category labels can split an issue across names. The comparison uses the latest five observed same-calendar-month rows, not necessarily five consecutive calendar years. Interpret any candidate in that light. The screen does not establish representativeness: CFPB complaint data are not a census of consumer experiences.

## Reproduction and method

Run `make run` to download/hash the public CFPB structured archive, scan full-source monthly counts and totals, apply the 15-day completeness rule, and write local aggregates. `make report` regenerates this report and chart from those outputs. The SQLite view is defined in [`sql/monthly_issue_trends.sql`](../sql/monthly_issue_trends.sql) and executed by [`src/cfpb_pipeline.py`](../src/cfpb_pipeline.py). The query divides full-source issue counts by full-source valid-date monthly totals; the 100,000-row sample is stored separately and is not the share denominator.

This report contains aggregate counts only. It does not contain complaint text or identifiers.
"""
    PORTFOLIO_REPORT_PATH.write_text(structured_report, encoding="utf-8")
    print(f"Wrote report to {PORTFOLIO_REPORT_PATH}")


if __name__ == "__main__":
    generate()

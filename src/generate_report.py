from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter
import pandas as pd

try:
    from .cfpb_pipeline import screen_issue_month
except ImportError:
    from cfpb_pipeline import screen_issue_month


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "output"
MANIFEST_PATH = PROJECT_DIR / "CFPB_DATA_MANIFEST.json"
TRENDS_PATH = OUTPUT_DIR / "issue_trends_monthly.csv"
CANDIDATES_PATH = OUTPUT_DIR / "emerging_issue_candidates.csv"
NARRATIVE_METRICS_PATH = OUTPUT_DIR / "cfpb_narrative_model_metrics.json"
REPORTS_DIR = PROJECT_DIR / "reports"
PORTFOLIO_REPORT_PATH = REPORTS_DIR / "structured_trends.md"
PORTFOLIO_CHART_PATH = REPORTS_DIR / "issue_trends.png"
YEAR_OVER_YEAR_SQL_PATH = PROJECT_DIR / "sql" / "year_over_year_issue_comparison.sql"
FEATURED_ISSUE = "Incorrect information on your report"


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


def build_featured_issue_series(
    trends: pd.DataFrame,
    issue: str,
    last_complete_month: str,
    window_months: int = 36,
) -> pd.DataFrame:
    latest = pd.Period(last_complete_month, freq="M")
    months = pd.period_range(latest - window_months + 1, latest, freq="M")
    issue_rows = trends.loc[
        (trends["issue"] == issue)
        & (trends["complaint_month"].astype(str).isin(months.astype(str))),
        ["complaint_month", "complaint_share"],
    ].copy()
    issue_rows["complaint_month"] = pd.PeriodIndex(
        issue_rows["complaint_month"], freq="M"
    )
    return (
        issue_rows.set_index("complaint_month")
        .reindex(months)
        .rename_axis("complaint_month")
        .reset_index()
    )


def query_year_over_year_comparison(
    database_path: Path,
    issue: str,
    current_month: str,
) -> dict[str, object]:
    current = pd.Period(current_month, freq="M")
    prior_year_month = str(current - 12)
    sql = YEAR_OVER_YEAR_SQL_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            sql,
            {
                "current_month": str(current),
                "prior_year_month": prior_year_month,
                "issue": issue,
            },
        )
        row = cursor.fetchone()
        columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row, strict=True))


def format_count(value: object) -> str:
    return f"{int(value):,}" if pd.notna(value) else "Missing"


def render_featured_issue_chart(
    series: pd.DataFrame,
    issue: str,
    current_month: str,
    prior_year_month: str,
    output_path: Path,
) -> None:
    color = "#0072B2"
    plotted = series.copy()
    plotted["date"] = pd.PeriodIndex(plotted["complaint_month"], freq="M").to_timestamp()
    plotted["date"] += pd.offsets.MonthEnd(0)
    latest = pd.Period(current_month, freq="M")
    prior = pd.Period(prior_year_month, freq="M")

    fig, ax = plt.subplots(figsize=(10, 6), facecolor="white")
    ax.set_facecolor("white")
    ax.plot(
        plotted["date"],
        plotted["complaint_share"],
        color=color,
        linewidth=2.6,
        solid_capstyle="round",
        zorder=2,
    )

    observations = plotted.set_index(pd.PeriodIndex(plotted["complaint_month"], freq="M"))
    for period, label, offset in (
        (prior, "One year earlier", (-8, -50)),
        (latest, "Latest complete month", (-8, 15)),
    ):
        value = (
            observations.loc[period, "complaint_share"]
            if period in observations.index
            else float("nan")
        )
        date = period.to_timestamp() + pd.offsets.MonthEnd(0)
        if pd.notna(value):
            ax.scatter([date], [value], color=color, s=48, zorder=3)
            text = f"{label}: {period.strftime('%b %Y')} · {value:.2%}"
            ax.annotate(
                text,
                (date, value),
                xytext=offset,
                textcoords="offset points",
                ha="right",
                va="center",
                fontsize=13,
                color="#202124",
                arrowprops={"arrowstyle": "-", "color": color, "lw": 0.9},
                bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": color, "lw": 0.8},
                zorder=4,
            )
        else:
            ax.text(
                0.99,
                0.03 if period == prior else 0.10,
                f"{label}: {period.strftime('%b %Y')} has no observed row",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=11,
                color="#4b5563",
            )

    ax.set_title(
        f"Monthly share assigned to “{issue}”",
        loc="left",
        fontsize=18,
        color="#202124",
        pad=14,
    )
    ax.set_ylabel("Share of valid-date complaints", color="#202124", fontsize=12)
    ax.set_xlabel("")
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(axis="y", color="#d9dee5", linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.tick_params(axis="both", colors="#4b5563", labelsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c5cbd3")
    ax.set_xlim(plotted["date"].min(), plotted["date"].max() + pd.Timedelta(days=115))
    ax.margins(y=0.14)
    fig.text(
        0.01,
        0.015,
        f"Source: CFPB Consumer Complaint Database · {issue} · "
        f"{plotted['complaint_month'].min()}–{current_month} · complete months only",
        ha="left",
        va="bottom",
        fontsize=10,
        color="#4b5563",
    )
    fig.subplots_adjust(left=0.11, right=0.98, top=0.88, bottom=0.18)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, facecolor="white")
    plt.close(fig)


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
    top_issues, _ = build_trend_chart_data(trends, str(latest_period))
    featured_series = build_featured_issue_series(
        trends, FEATURED_ISSUE, str(latest_period)
    )
    current_month = str(latest_period)
    prior_year_month = str(latest_period - 12)
    comparison = query_year_over_year_comparison(
        PROJECT_DIR / "complaints_warehouse.db",
        FEATURED_ISSUE,
        current_month,
    )
    render_featured_issue_chart(
        featured_series,
        FEATURED_ISSUE,
        current_month,
        prior_year_month,
        PORTFOLIO_CHART_PATH,
    )
    screen_candidates, screen_counts = screen_issue_month(
        trends, current_month
    )

    missingness = summary.get("missingness_rate_by_field", {})
    missingness_table = "\n".join(
        f"| `{field}` | {rate:.3%} |"
        for field, rate in missingness.items()
        if rate is not None
    ) or "| No full-archive missingness figures available | n/a |"
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

    current_share = comparison["current_issue_share"]
    prior_share = comparison["prior_year_issue_share"]
    share_change_pp = comparison["share_change_percentage_points"]
    current_share_text = f"{current_share:.2%}" if current_share is not None else "No recorded issue row"
    prior_share_text = f"{prior_share:.2%}" if prior_share is not None else "No recorded issue row"
    change_text = f"{share_change_pp:+.2f} pp" if share_change_pp is not None else "Unavailable (comparison row missing)"

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

The featured issue is `{FEATURED_ISSUE}`. The chart shows its monthly share over the latest 36 complete months available in this snapshot; missing issue-month observations are left as gaps. The comparison below is generated by the parameterized SQL query in `sql/year_over_year_issue_comparison.sql`, using the full-source aggregate tables.

| Period | Issue count | Valid-date complaints | Issue share |
|---|---:|---:|---:|
| {comparison['current_month']} | {format_count(comparison['current_issue_count'])} | {format_count(comparison['current_total_complaints'])} | {current_share_text} |
| {comparison['prior_year_month']} | {format_count(comparison['prior_year_issue_count'])} | {format_count(comparison['prior_year_total_complaints'])} | {prior_share_text} |

Change in share: **{change_text}**. Both issue shares use all complaints with valid received dates in the corresponding calendar month as the denominator. The difference is current share minus prior-year share, in percentage points.

![Monthly share of CFPB complaints labeled {FEATURED_ISSUE}, with {current_month} and {prior_year_month} values marked, over 36 complete months](issue_trends.png)

## Exploratory candidates

For {latest_month}, the existing screen observed {screen_counts['observed_issue_labels']} distinct issue labels. {screen_counts['eligible_issue_labels']} met both screening eligibility rules (at least 50 complaints and at least three prior observed same-calendar-month rows); {screen_counts['flagged_issue_labels']} were flagged at three or more historical sample standard deviations. This is a screening heuristic, not a significance test or an incident detector.

| Issue | Count | All complaints that month | Observed share | Mean comparison share | Historical months used |
|---|---:|---:|---:|---:|---|
{chr(10).join(
    f"| {row.issue} | {int(row.complaint_count):,} | {int(row.monthly_denominator):,} | "
    f"{row.complaint_share:.3%} | {row.seasonal_baseline_share:.3%} | {row.baseline_months} |"
    for row in screen_candidates.itertuples(index=False)
) or "| No issue met the screening rule in this month | | | | | |"}

The most recent earlier flag was in June 2026: `Problem with a company's investigation into an existing issue` had 922 of 620,905 complaints (0.1485%), versus a 0.0621% mean for the observed June 2021–2025 rows. The exact candidate label appears in all five rows. A similarly named investigation category (`Problem with a company's investigation into an existing problem`) is counted separately and had 113,635 June 2026 complaints. Category names are not harmonized; this flag alone does not establish a substantive increase.

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
    candidate_lines = []
    for row in screen_candidates.itertuples(index=False):
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
    candidate_result = "\n".join(candidate_lines) or (
        "| No issues met the screening rule in the latest complete month | | | | | |"
    )
    structured_report = f"""# CFPB structured complaint trends

**Snapshot received-date coverage through:** {snapshot_date}<br>
**Retrieved:** {retrieval_date}<br>
**Latest complete complaint month under the maturity rule:** {latest_period}

## What the trend shows

The chart below shows the monthly share for `{FEATURED_ISSUE}` over the latest 36 complete months. Counts and monthly denominators are full-source aggregates over valid complaint dates, not the capped local sample. Shares are each issue's count divided by all complaints with a valid received date in that calendar month. Missing issue-month observations are shown as gaps.

![Monthly share of CFPB complaints labeled {FEATURED_ISSUE}, with {current_month} and {prior_year_month} values marked, over 36 complete months](issue_trends.png)

## Same-month year-over-year comparison

The SQL query in [`../sql/year_over_year_issue_comparison.sql`](../sql/year_over_year_issue_comparison.sql) compares exact issue-label and calendar-month matches in the full-source aggregates.

| Period | Issue count | Valid-date complaints | Issue share |
|---|---:|---:|---:|
| {comparison['current_month']} | {format_count(comparison['current_issue_count'])} | {format_count(comparison['current_total_complaints'])} | {current_share_text} |
| {comparison['prior_year_month']} | {format_count(comparison['prior_year_issue_count'])} | {format_count(comparison['prior_year_total_complaints'])} | {prior_share_text} |

Change in share: **{change_text}** (current minus prior-year share). A missing aggregate row remains missing; it is not interpreted as zero.

## Screening result for {latest_period}

The existing exploratory screen observed {screen_counts['observed_issue_labels']} distinct issue labels in this month. {screen_counts['eligible_issue_labels']} qualified under the count threshold (at least 50) and historical-coverage rule (at least three prior **observed** same-calendar-month rows); {screen_counts['flagged_issue_labels']} were flagged at a rise of at least three sample standard deviations. This is a prompt for investigation, not a significance test, incident finding, causal result, or evidence of consumer harm.

| Issue | Count | All complaints that month | Observed share | Mean comparison share | Historical months used |
|---|---:|---:|---:|---:|---|
{candidate_result}

{recent_candidate_section}

Missing issue-month rows are not zero-filled by the existing comparison; absent rows may reflect zero recorded counts, while changed category labels can split an issue across names. The comparison uses the latest five observed same-calendar-month rows, not necessarily five consecutive calendar years. Interpret any candidate in that light. The screen does not establish representativeness: CFPB complaint data are not a census of consumer experiences.

## Reproduction and method

Run `make run` to download/hash the public CFPB structured archive, scan full-source monthly counts and totals, apply the 15-day completeness rule, and write local aggregates. `make report` regenerates this report and chart from those outputs. The monthly SQLite view is defined in [`../sql/monthly_issue_trends.sql`](../sql/monthly_issue_trends.sql) and executed by [`../src/cfpb_pipeline.py`](../src/cfpb_pipeline.py). The year-over-year query is executed by the report generator against those same full-source aggregates; the 100,000-row sample is stored separately and is not the share denominator.

This report contains aggregate counts only. It does not contain complaint text or identifiers.
"""
    PORTFOLIO_REPORT_PATH.write_text(structured_report, encoding="utf-8")
    print(f"Wrote report to {PORTFOLIO_REPORT_PATH}")


if __name__ == "__main__":
    generate()

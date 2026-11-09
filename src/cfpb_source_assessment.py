from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from .cfpb_pipeline import load_source_sample
except ImportError:
    from cfpb_pipeline import load_source_sample

SOURCE_PAGE = "https://www.consumerfinance.gov/data-research/consumer-complaints/"


def summarize_source(
    df: pd.DataFrame,
    source_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    source_metadata = source_metadata or {}
    narrative_candidates = [
        column
        for column in df.columns
        if any(marker in column.lower() for marker in ("narr", "story", "what_happened", "complaint_text"))
    ]

    sample_dates = pd.to_datetime(df.get("Date received", pd.Series(dtype="datetime64[ns]")), errors="coerce")
    sample_latest_date = sample_dates.max()
    latest_date_value = source_metadata.get(
        "latest_complaint_date",
        sample_latest_date.strftime("%Y-%m-%d") if pd.notna(sample_latest_date) else None,
    )
    latest_narrative_value = None

    review_redaction = {
        "contains_redacted_narratives": None,
        "narrative_columns": narrative_candidates,
        "assessment": "No narrative field is available in this source snapshot, so redaction within narratives cannot be assessed.",
    }
    full_missing = source_metadata.get("missing_values_by_field", {})
    source_rows = int(source_metadata.get("source_rows_scanned", len(df)))
    reported_missingness = {
        column: (float(full_missing[column]) / source_rows if source_rows else None)
        for column in ["Date received", "Product", "Issue", "Company", "Sub-product", "State", "Tags"]
        if column in full_missing
    }
    retrieval_timestamp = source_metadata.get(
        "retrieval_timestamp_utc",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    latest_gap_days = None
    if latest_date_value:
        retrieval_date = pd.Timestamp(retrieval_timestamp).date()
        latest_gap_days = (retrieval_date - pd.Timestamp(latest_date_value).date()).days

    publication_policy = {
        "website_statement": (
            "Complaints sent to companies for response are published after the company responds and "
            "confirms a commercial relationship, or after 15 days, whichever comes first. "
            "The database generally updates daily and is not representative of all marketplace experiences."
        ),
        "observed_publication_lag_days": None,
        "notes": "The archive does not expose a public release timestamp for each complaint. The observed gap between the latest complaint date and retrieval date is not a measured publication lag.",
    }

    return {
        "source": SOURCE_PAGE,
        "retrieval_method": "Official full CFPB bulk CSV ZIP download; streamed in 200,000-row chunks",
        "retrieval_timestamp_utc": retrieval_timestamp,
        "query_parameters": {"date_filters": None, "row_limit": None},
        "source_update_frequency": "Daily",
        "source_documentation": [
            "https://cfpb.github.io/api/ccdb/",
            "https://cfpb.github.io/api/ccdb/fields.html",
            "https://cfpb.github.io/api/ccdb/release-notes.html",
        ],
        "source_columns": source_metadata.get("source_columns", df.columns.tolist()),
        "dataset_summary": {
            "row_count": source_rows,
            "sample_row_count": int(len(df)),
            "earliest_complaint_date": source_metadata.get("earliest_complaint_date"),
            "latest_complaint_date": latest_date_value,
            "latest_usable_narrative_date": latest_narrative_value,
            "retrieval_to_latest_complaint_date_gap_days": latest_gap_days,
            "missingness_rate_by_field": reported_missingness,
            "monthly_row_counts": source_metadata.get("monthly_row_counts", {}),
            "monthly_issue_counts": source_metadata.get("monthly_issue_counts", []),
            "issue_taxonomy_by_year": source_metadata.get("issue_taxonomy_by_year", {}),
        },
        "publication_policy": publication_policy,
        "narrative_availability": {
            "public_bulk_export_has_narrative_text": False,
            "candidate_narrative_columns": source_metadata.get(
                "narrative_field_candidates",
                narrative_candidates,
            ),
            "reason": (
                "The downloaded bulk schema and dated API records contain no narrative field. "
                "The official CFPB API release notes explicitly state that consumer complaint narratives "
                "were removed from the database."
            ),
        },
        "modeling_status": "Empirical modeling is incomplete. Narrative classification is blocked because source text is unavailable.",
        "structured_issue_classifier": {
            "trained": False,
            "evaluation_metrics": None,
            "reason": "Structured issue analysis is not a substitute for the requested narrative classifier.",
        },
        "data_quality_checks": {
            "duplicate_complaint_ids_in_sample": int(source_metadata.get("duplicate_complaint_ids_in_sample", 0)),
            "missing_date_received_full_archive": int(full_missing.get("Date received", 0)),
            "missing_issue_full_archive": int(full_missing.get("Issue", 0)),
            "missing_company_full_archive": int(full_missing.get("Company", 0)),
            "redaction_artifacts": review_redaction,
        },
        "snapshot": {
            "archive_sha256": source_metadata.get("source_sha256"),
            "source_rows_scanned": source_rows,
            "sample_method": source_metadata.get("sample_method"),
            "sample_rows": int(len(df)),
        },
        "reproducible_refresh": {
            "download_command": "python src/cfpb_pipeline.py --refresh-source --refresh-sample",
            "notes": "The official archive is downloaded to output/complaints.csv.zip, SHA-256 hashed, and scanned in chunks. No narrative data or model artifacts are produced.",
        },
    }


def generate_report(output_dir: Path, max_rows: int | None = None, refresh: bool = False) -> dict[str, object]:
    df, source_metadata = load_source_sample(
        max_sample_rows=max_rows or 100_000,
        refresh_source=refresh,
        refresh_sample=refresh,
    )
    report = summarize_source(df, source_metadata)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_json = Path(__file__).resolve().parents[1] / "CFPB_DATA_MANIFEST.json"
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assess CFPB source and write a reproducible data manifest.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "output")
    parser.add_argument("--max-rows", type=int, default=100_000, help="Maximum persisted metadata sample rows; full archive is still scanned for source counts.")
    parser.add_argument("--refresh", action="store_true", help="Redownload the ZIP archive instead of reusing a cached file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = generate_report(args.output_dir, max_rows=args.max_rows, refresh=args.refresh)
    print(json.dumps(report["dataset_summary"], indent=2, default=str))


if __name__ == "__main__":
    main()

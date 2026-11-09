from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "output"
ARCHIVE_PATH = OUTPUT_DIR / "complaints.csv.zip"
SAMPLE_PATH = OUTPUT_DIR / "cfpb_source_sample.parquet"
SAMPLE_METADATA_PATH = OUTPUT_DIR / "cfpb_source_sample.json"
DATABASE_PATH = PROJECT_DIR / "complaints_warehouse.db"
MANIFEST_PATH = PROJECT_DIR / "CFPB_DATA_MANIFEST.json"
DATA_URL = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
SOURCE_PAGE = "https://www.consumerfinance.gov/data-research/consumer-complaints/"
SAMPLE_LIMIT = 100_000
SAMPLE_SEED = 427
CHUNK_SIZE = 200_000
SAMPLE_VERSION = 1
SOURCE_FIELDS = {
    "Date received", "Product", "Sub-product", "Issue", "Sub-issue",
    "Company public response", "Company", "State", "ZIP code", "Tags",
    "Submitted via", "Date sent to company", "Company response to consumer",
    "Timely response?", "Complaint ID",
}
SAMPLE_FIELDS = [
    "Date received",
    "Product",
    "Sub-product",
    "Issue",
    "Submitted via",
    "Complaint ID",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_archive(refresh: bool = False) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if refresh or not ARCHIVE_PATH.exists():
        temporary_path = ARCHIVE_PATH.with_suffix(".zip.part")
        urllib.request.urlretrieve(DATA_URL, temporary_path)
        temporary_path.replace(ARCHIVE_PATH)
    return ARCHIVE_PATH


def load_source_sample(
    refresh_source: bool = False,
    refresh_sample: bool = False,
    max_sample_rows: int = SAMPLE_LIMIT,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if max_sample_rows < 1:
        raise ValueError("max_sample_rows must be greater than zero.")
    if max_sample_rows > SAMPLE_LIMIT:
        raise ValueError(f"max_sample_rows cannot exceed the configured {SAMPLE_LIMIT:,}-row cap.")
    archive_path = download_archive(refresh=refresh_source)
    source_hash = sha256_file(archive_path)
    if not refresh_sample and SAMPLE_PATH.exists() and SAMPLE_METADATA_PATH.exists():
        cached_metadata = json.loads(SAMPLE_METADATA_PATH.read_text(encoding="utf-8"))
        if (
            cached_metadata.get("sample_version") == SAMPLE_VERSION
            and cached_metadata.get("source_sha256") == source_hash
        ):
            sample = pd.read_parquet(SAMPLE_PATH)
            sample["Date received"] = pd.to_datetime(sample["Date received"], errors="coerce")
            if len(sample) > max_sample_rows:
                sample = sample.sample(n=max_sample_rows, random_state=SAMPLE_SEED)
                sample = sample.sort_values("Date received").reset_index(drop=True)
            return sample, cached_metadata

    missingness: dict[str, int] = {}
    monthly_totals: dict[str, int] = {}
    monthly_issues: dict[tuple[str, str], int] = {}
    issue_categories_by_year: dict[str, set[str]] = {}
    sample_chunks: list[pd.DataFrame] = []
    source_rows = 0
    earliest_date: pd.Timestamp | None = None
    latest_date: pd.Timestamp | None = None

    with zipfile.ZipFile(archive_path) as archive:
        csv_name = archive.namelist()[0]
        with archive.open(csv_name) as header_handle:
            source_columns = pd.read_csv(header_handle, nrows=0).columns.tolist()
        missing_required = sorted(set(SAMPLE_FIELDS).difference(source_columns))
        if missing_required:
            raise ValueError(f"CFPB archive is missing required fields: {missing_required}")
        missingness = {field: 0 for field in source_columns if field in SOURCE_FIELDS}
        narrative_fields = [
            column
            for column in source_columns
            if any(token in column.lower() for token in ("narr", "story", "what_happened", "complaint_text"))
        ]

        with archive.open(csv_name) as file_handle:
            for chunk in pd.read_csv(
                file_handle,
                usecols=lambda column: column in SOURCE_FIELDS,
                chunksize=CHUNK_SIZE,
                low_memory=False,
            ):
                source_rows += len(chunk)
                for field in missingness:
                    missingness[field] += int(chunk[field].isna().sum())
                dates = pd.to_datetime(chunk["Date received"], errors="coerce")
                valid_dates = dates.notna()
                if valid_dates.any():
                    chunk_min = dates[valid_dates].min()
                    chunk_max = dates[valid_dates].max()
                    earliest_date = chunk_min if earliest_date is None else min(earliest_date, chunk_min)
                    latest_date = chunk_max if latest_date is None else max(latest_date, chunk_max)
                    month_values = dates[valid_dates].dt.to_period("M").astype(str)
                    for month, count in month_values.value_counts().items():
                        month = str(month)
                        monthly_totals[month] = monthly_totals.get(month, 0) + int(count)
                    issue_values = chunk.loc[valid_dates, "Issue"].fillna("Unknown").astype(str)
                    monthly_frame = pd.DataFrame(
                        {"month": month_values.to_numpy(), "issue": issue_values.to_numpy()}
                    )
                    for (month, issue), count in monthly_frame.groupby(
                        ["month", "issue"], sort=False
                    ).size().items():
                        key = (str(month), str(issue))
                        monthly_issues[key] = monthly_issues.get(key, 0) + int(count)
                        issue_categories_by_year.setdefault(str(month)[:4], set()).add(str(issue))

                    complaint_ids = chunk.loc[valid_dates, "Complaint ID"].fillna("").astype(str)
                    selected = (
                        pd.util.hash_pandas_object(complaint_ids, index=False).to_numpy(dtype="uint64") % 100
                    ) == 0
                    selected_rows = chunk.loc[valid_dates].loc[selected, SAMPLE_FIELDS].copy()
                    selected_rows["Date received"] = dates[valid_dates].loc[selected].to_numpy()
                    if not selected_rows.empty:
                        sample_chunks.append(selected_rows)

    if not sample_chunks:
        raise ValueError("The CFPB archive did not contain any complaint rows with usable dates.")
    sample_with_id = pd.concat(sample_chunks, ignore_index=True)
    if len(sample_with_id) > max_sample_rows:
        sample_with_id = sample_with_id.sample(n=max_sample_rows, random_state=SAMPLE_SEED)
    duplicate_ids = int(sample_with_id["Complaint ID"].duplicated().sum())
    sample = sample_with_id.drop(columns="Complaint ID")
    sample["Date received"] = pd.to_datetime(sample["Date received"], errors="coerce")
    sample = sample.sort_values("Date received").reset_index(drop=True)
    sample.to_parquet(SAMPLE_PATH, index=False)

    metadata: dict[str, object] = {
        "source_url": DATA_URL,
        "source_page": SOURCE_PAGE,
        "source_sha256": source_hash,
        "retrieval_timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "source_rows_scanned": source_rows,
        "earliest_complaint_date": earliest_date.strftime("%Y-%m-%d") if earliest_date is not None else None,
        "latest_complaint_date": latest_date.strftime("%Y-%m-%d") if latest_date is not None else None,
        "sample_rows": int(len(sample)),
        "sample_limit": max_sample_rows,
        "sample_seed": SAMPLE_SEED,
        "sample_method": (
            "Deterministic 1-in-100 hash sample keyed by CFPB Complaint ID, then "
            "uniformly capped at the configured sample limit; complaint IDs are removed before persistence."
        ),
        "duplicate_complaint_ids_in_sample": duplicate_ids,
        "sample_version": SAMPLE_VERSION,
        "source_columns": source_columns,
        "narrative_field_candidates": narrative_fields,
        "missing_values_by_field": missingness,
        "monthly_row_counts": {str(key): int(value) for key, value in monthly_totals.items()},
        "monthly_issue_counts": [
            {"month": month, "issue": issue, "count": count}
            for (month, issue), count in sorted(monthly_issues.items())
        ],
        "issue_taxonomy_by_year": {
            year: sorted(categories) for year, categories in sorted(issue_categories_by_year.items())
        },
    }
    SAMPLE_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return sample, metadata


def latest_mature_month(metadata: dict[str, object]) -> tuple[pd.Period, pd.Timestamp]:
    latest = pd.Timestamp(metadata["latest_complaint_date"])
    retrieved = pd.Timestamp(metadata["retrieval_timestamp_utc"]).tz_convert(None)
    maturity_cutoff = min(latest, retrieved - pd.Timedelta(days=15))
    mature_month = maturity_cutoff.to_period("M")
    if maturity_cutoff.normalize() < mature_month.end_time.normalize():
        mature_month -= 1
    return mature_month, maturity_cutoff


def build_sqlite_warehouse(
    sample: pd.DataFrame,
    metadata: dict[str, object],
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Connection:
    if database_path.exists():
        database_path.unlink()
    connection = sqlite3.connect(database_path)
    sample.to_sql("complaint_sample", connection, index=False, if_exists="replace")
    pd.DataFrame(metadata["monthly_issue_counts"]).to_sql(
        "source_monthly_issue_counts", connection, index=False, if_exists="replace"
    )
    pd.DataFrame(
        [
            {"month": month, "complaint_count": count}
            for month, count in metadata["monthly_row_counts"].items()
        ]
    ).to_sql("source_monthly_totals", connection, index=False, if_exists="replace")
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_complaint_sample_date
            ON complaint_sample("Date received");
        CREATE INDEX IF NOT EXISTS idx_source_issue_month
            ON source_monthly_issue_counts(month, issue);

        CREATE VIEW vw_monthly_issue_trends AS
        SELECT
            i.month AS complaint_month,
            i.issue AS issue,
            i.count AS complaint_count,
            t.complaint_count AS monthly_denominator,
            1.0 * i.count / t.complaint_count AS complaint_share
        FROM source_monthly_issue_counts AS i
        JOIN source_monthly_totals AS t ON i.month = t.month;
        """
    )
    connection.commit()
    return connection


def find_emerging_issue_candidates(
    trends: pd.DataFrame,
    last_complete_month: str,
    minimum_count: int = 50,
) -> pd.DataFrame:
    data = trends.copy()
    data["complaint_month"] = pd.PeriodIndex(data["complaint_month"], freq="M")
    data = data[data["complaint_month"] <= pd.Period(last_complete_month, freq="M")]
    candidates: list[dict[str, object]] = []
    for row in data.itertuples(index=False):
        baseline = data[
            (data["issue"] == row.issue)
            & (data["complaint_month"].dt.month == row.complaint_month.month)
            & (data["complaint_month"] < row.complaint_month)
        ].tail(5)
        if len(baseline) < 3 or row.complaint_count < minimum_count:
            continue
        mean_share = float(baseline["complaint_share"].mean())
        std_share = float(baseline["complaint_share"].std(ddof=1))
        if std_share == 0:
            if row.complaint_share <= mean_share:
                continue
            z_score = float("inf")
        else:
            z_score = (float(row.complaint_share) - mean_share) / std_share
        if z_score >= 3:
            candidates.append(
                {
                    "complaint_month": str(row.complaint_month),
                    "issue": row.issue,
                    "complaint_count": int(row.complaint_count),
                    "monthly_denominator": int(row.monthly_denominator),
                    "complaint_share": round(float(row.complaint_share), 6),
                    "seasonal_baseline_share": round(mean_share, 6),
                    "seasonal_z_score": round(z_score, 3) if np.isfinite(z_score) else None,
                    "interpretation": "Pattern for analyst investigation; not a verified incident or evidence of harm.",
                }
            )
    columns = [
        "complaint_month", "issue", "complaint_count", "monthly_denominator",
        "complaint_share", "seasonal_baseline_share", "seasonal_z_score", "interpretation",
    ]
    if not candidates:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(candidates, columns=columns).sort_values(
        ["complaint_month", "seasonal_z_score"], ascending=[False, False], na_position="last"
    )


def run(
    refresh_source: bool = False,
    refresh_sample: bool = False,
    max_sample_rows: int = SAMPLE_LIMIT,
) -> dict[str, object]:
    sample, metadata = load_source_sample(
        refresh_source=refresh_source,
        refresh_sample=refresh_sample,
        max_sample_rows=max_sample_rows,
    )
    connection = build_sqlite_warehouse(sample, metadata)
    trends = pd.read_sql_query("SELECT * FROM vw_monthly_issue_trends ORDER BY complaint_month, issue", connection)
    connection.close()

    mature_month, maturity_cutoff = latest_mature_month(metadata)
    trends = trends[trends["complaint_month"] <= str(mature_month)].copy()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trends.to_csv(OUTPUT_DIR / "issue_trends_monthly.csv", index=False)
    candidates = find_emerging_issue_candidates(trends, str(mature_month))
    candidates.to_csv(OUTPUT_DIR / "emerging_issue_candidates.csv", index=False)

    try:
        from .cfpb_source_assessment import summarize_source
    except ImportError:
        from cfpb_source_assessment import summarize_source

    manifest = summarize_source(sample, metadata)
    manifest["evaluation_maturity"] = {
        "last_complete_month": str(mature_month),
        "maturity_cutoff_date": maturity_cutoff.strftime("%Y-%m-%d"),
        "rule": "Require 15 days of publication maturity and exclude a month unless its end is mature.",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "cfpb_source_assessment.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    quality = {
        "source_rows_scanned": metadata["source_rows_scanned"],
        "persisted_sample_rows": len(sample),
        "sample_duplicate_complaint_ids": metadata["duplicate_complaint_ids_in_sample"],
        "sample_missing_values": {
            column: int(sample[column].isna().sum()) for column in sample.columns
        },
        "sample_earliest_date": sample["Date received"].min().strftime("%Y-%m-%d"),
        "sample_latest_date": sample["Date received"].max().strftime("%Y-%m-%d"),
        "narrative_fields_available": bool(metadata["narrative_field_candidates"]),
        "narrative_modeling_status": (
            "Empirical modeling is incomplete. Narrative classification is blocked because source text is unavailable."
        ),
    }
    (OUTPUT_DIR / "cfpb_data_quality.json").write_text(
        json.dumps(quality, indent=2), encoding="utf-8"
    )
    result = {
        "source_rows_scanned": metadata["source_rows_scanned"],
        "sample_rows": len(sample),
        "earliest_complaint_date": metadata["earliest_complaint_date"],
        "latest_complaint_date": metadata["latest_complaint_date"],
        "narrative_fields": metadata["narrative_field_candidates"],
        "last_complete_month": str(mature_month),
        "emerging_issue_candidates": len(candidates),
        "manifest_path": str(MANIFEST_PATH),
    }
    print(json.dumps(result, indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan CFPB public data and build a local source manifest and SQL trend tables.")
    parser.add_argument("--refresh-source", action="store_true", help="Download a fresh CFPB archive.")
    parser.add_argument("--refresh-sample", action="store_true", help="Rescan the archive and rebuild the deterministic sample and aggregates.")
    parser.add_argument("--max-sample-rows", type=int, default=SAMPLE_LIMIT)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        refresh_source=args.refresh_source,
        refresh_sample=args.refresh_sample,
        max_sample_rows=args.max_sample_rows,
    )

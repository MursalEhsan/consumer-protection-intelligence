from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import re
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "output"
ARCHIVE_DIR = OUTPUT_DIR / "cfpb_narrative_archives"
SAMPLE_PATH = OUTPUT_DIR / "cfpb_narrative_sample.parquet"
SAMPLE_METADATA_PATH = OUTPUT_DIR / "cfpb_narrative_sample_manifest.json"
MODEL_PATH = PROJECT_DIR / "complaint_narrative_tfidf_logreg.joblib"
METRICS_PATH = OUTPUT_DIR / "cfpb_narrative_model_metrics.json"
MANIFEST_PATH = PROJECT_DIR / "CFPB_NARRATIVE_MODEL_MANIFEST.json"

ARCHIVE_PAGE = (
    "https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/"
    "cfpb-consumer-complaint-database-narratives-archive/"
)
SOURCE_FIELDS = [
    "Date received",
    "Product",
    "Issue",
    "Consumer complaint narrative",
    "Complaint ID",
]
REQUIRED_FIELDS = {
    "Date received",
    "Issue",
    "Consumer complaint narrative",
    "Complaint ID",
}
SAMPLE_SEED = 427
SAMPLE_LIMIT = 100_000
CHUNK_SIZE = 25_000
SPLIT_WEIGHTS = {"train": 0.60, "validation": 0.20, "test": 0.20}
SPLIT_PERIODS = {
    "train": ("2024-11-01", "2025-10-31"),
    "validation": ("2025-11-01", "2025-12-31"),
    "test": ("2026-01-01", "2026-08-14"),
}
OTHER_LABEL = "Other / outside selected training taxonomy"
TOP_TRAIN_LABELS = 10
MIN_TRAIN_LABEL_SUPPORT = 100

ARCHIVE_SOURCES = [
    {
        "filename": "CCDB_Export_1_December_2011_through_April_2018.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_1_December_2011_through_April_2018.zip",
    },
    {
        "filename": "CCDB_Export_8_November_2024_through_December_2024.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_8_November_2024_through_December_2024.zip",
    },
    {
        "filename": "CCDB_Export_9_January_2025_through_February_2025.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_9_January_2025_through_February_2025.zip",
    },
    {
        "filename": "CCDB_Export_10_March_2025_through_April_2025.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_10_March_2025_through_April_2025.zip",
    },
    {
        "filename": "CCDB_Export_11_May_2025_through_June_2025.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_11_May_2025_through_June_2025.zip",
    },
    {
        "filename": "CCDB_Export_12_July_2025_through_August_2025.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_12_July_2025_through_August_2025.zip",
    },
    {
        "filename": "CCDB_Export_13_September_2025_through_October_2025.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_13_September_2025_through_October_2025.zip",
    },
    {
        "filename": "CCDB_Export_14_November_2025_through_December_2025.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_14_November_2025_through_December_2025.zip",
    },
    {
        "filename": "CCDB_Export_15_January_2026_through_February_2026.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_15_January_2026_through_February_2026.zip",
    },
    {
        "filename": "CCDB_Export_16_March_2026.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_16_March_2026.zip",
    },
    {
        "filename": "CCDB_Export_17_April_2026.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_17_April_2026.zip",
    },
    {
        "filename": "CCDB_Export_18_May_2026.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_18_May_2026.zip",
    },
    {
        "filename": "CCDB_Export_19_June_2026.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_19_June_2026.zip",
    },
    {
        "filename": "CCDB_Export_20_July_2026.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_20_July_2026.zip",
    },
    {
        "filename": "CCDB_Export_21_August_2026.zip",
        "url": "https://files.consumerfinance.gov/f/documents/CCDB_Export_21_August_2026.zip",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_archives(refresh: bool = False) -> list[dict[str, str]]:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    local_sources = []
    for source in ARCHIVE_SOURCES:
        path = ARCHIVE_DIR / source["filename"]
        if refresh or not path.exists():
            temporary_path = path.with_suffix(".zip.part")
            urlretrieve(source["url"], temporary_path)
            temporary_path.replace(path)
        local_sources.append({**source, "path": str(path)})

    august_path = OUTPUT_DIR / "CCDB_Export_21_August_2026.zip"
    if august_path.exists():
        archived = next(
            item for item in local_sources if item["filename"].startswith("CCDB_Export_21_")
        )
        if sha256_file(august_path) != sha256_file(Path(archived["path"])):
            raise ValueError(
                "Two different local copies of the August 2026 export were found; "
                "resolve the source snapshot before modeling."
            )
    return local_sources


def split_for_date(value: pd.Timestamp) -> str | None:
    if pd.isna(value):
        return None
    date_text = value.strftime("%Y-%m-%d")
    for split_name, (start, end) in SPLIT_PERIODS.items():
        if start <= date_text <= end:
            return split_name
    return None


def sample_rank(complaint_id: str, seed: int = SAMPLE_SEED) -> int:
    payload = f"{seed}:{complaint_id}".encode("utf-8")
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big")


def sample_quotas(max_rows: int = SAMPLE_LIMIT) -> dict[str, int]:
    if not 1 <= max_rows <= SAMPLE_LIMIT:
        raise ValueError(f"max_rows must be between 1 and {SAMPLE_LIMIT:,}.")
    train = int(max_rows * SPLIT_WEIGHTS["train"])
    validation = int(max_rows * SPLIT_WEIGHTS["validation"])
    return {
        "train": train,
        "validation": validation,
        "test": max_rows - train - validation,
    }


def normalize_narrative(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).casefold()).strip()


def collect_archived_sample(
    local_sources: list[dict[str, str]],
    max_rows: int = SAMPLE_LIMIT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    quotas = sample_quotas(max_rows)
    heaps: dict[str, list[tuple[int, int, tuple[str, str, str, str, str]]]] = {
        split_name: [] for split_name in quotas
    }
    archive_summaries: list[dict[str, Any]] = []
    all_issue_labels_by_year: dict[str, set[str]] = defaultdict(set)
    eligible_issue_counts_by_year: dict[str, Counter[str]] = defaultdict(Counter)
    source_issue_counts_by_year: dict[str, Counter[str]] = defaultdict(Counter)
    all_month_counts: Counter[str] = Counter()
    eligible_month_counts: Counter[str] = Counter()
    split_eligible_counts: Counter[str] = Counter()
    row_sequence = 0

    for source in local_sources:
        path = Path(source["path"])
        if not path.exists():
            raise FileNotFoundError(f"CFPB archive is missing: {path}")
        source_rows = 0
        missing_counts = Counter()
        earliest: pd.Timestamp | None = None
        latest: pd.Timestamp | None = None
        source_month_counts: Counter[str] = Counter()
        source_eligible_by_month: Counter[str] = Counter()
        with zipfile.ZipFile(path) as archive:
            csv_members = [member for member in archive.infolist() if member.filename.lower().endswith(".csv")]
            if len(csv_members) != 1:
                raise ValueError(
                    f"Expected exactly one CSV in {path.name}, found {len(csv_members)}."
                )
            member = csv_members[0]
            with archive.open(member) as header_handle:
                source_columns = pd.read_csv(header_handle, nrows=0).columns.tolist()
            missing_required = sorted(REQUIRED_FIELDS.difference(source_columns))
            if missing_required:
                raise ValueError(
                    f"{path.name} is missing required narrative fields: {missing_required}"
                )

            with archive.open(member) as handle:
                for chunk in pd.read_csv(
                    handle,
                    usecols=lambda column: column in SOURCE_FIELDS,
                    chunksize=CHUNK_SIZE,
                    low_memory=False,
                ):
                    source_rows += len(chunk)
                    for column in SOURCE_FIELDS:
                        if column in chunk:
                            missing_counts[column] += int(chunk[column].isna().sum())
                    dates = pd.to_datetime(chunk["Date received"], errors="coerce")
                    text = chunk["Consumer complaint narrative"].fillna("").astype(str).str.strip()
                    issue = chunk["Issue"].fillna("").astype(str).str.strip()
                    complaint_ids = chunk["Complaint ID"].fillna("").astype(str).str.strip()
                    valid_dates = dates.notna()
                    usable_text = text.ne("")
                    valid_issue = issue.ne("")
                    valid_ids = complaint_ids.ne("")
                    if valid_dates.any():
                        chunk_earliest = dates[valid_dates].min()
                        chunk_latest = dates[valid_dates].max()
                        earliest = chunk_earliest if earliest is None else min(earliest, chunk_earliest)
                        latest = chunk_latest if latest is None else max(latest, chunk_latest)
                        months = dates[valid_dates].dt.to_period("M").astype(str)
                        source_month_counts.update(months.tolist())
                        all_month_counts.update(months.tolist())
                        source_labels = issue[valid_dates & valid_issue]
                        source_years = dates[valid_dates & valid_issue].dt.year.astype(str)
                        for year, label in zip(source_years.tolist(), source_labels.tolist()):
                            source_issue_counts_by_year[year][label] += 1
                            all_issue_labels_by_year[year].add(label)

                    eligible = valid_dates & usable_text & valid_issue & valid_ids
                    if not eligible.any():
                        continue
                    eligible_dates = dates[eligible]
                    eligible_text = text[eligible]
                    eligible_issues = issue[eligible]
                    eligible_ids = complaint_ids[eligible]
                    eligible_months = eligible_dates.dt.to_period("M").astype(str)
                    source_eligible_by_month.update(eligible_months.tolist())
                    eligible_month_counts.update(eligible_months.tolist())
                    eligible_years = eligible_dates.dt.year.astype(str)
                    for year, label in zip(eligible_years.tolist(), eligible_issues.tolist()):
                        eligible_issue_counts_by_year[year][label] += 1

                    for date_value, narrative, label, complaint_id, month in zip(
                        eligible_dates.tolist(),
                        eligible_text.tolist(),
                        eligible_issues.tolist(),
                        eligible_ids.tolist(),
                        eligible_months.tolist(),
                    ):
                        split_name = split_for_date(pd.Timestamp(date_value))
                        if split_name is None:
                            continue
                        split_eligible_counts[split_name] += 1
                        quota = quotas[split_name]
                        rank = sample_rank(complaint_id)
                        row_sequence += 1
                        record = (
                            pd.Timestamp(date_value).strftime("%Y-%m-%d"),
                            str(label),
                            str(narrative),
                            source["filename"],
                            str(complaint_id),
                        )
                        heap = heaps[split_name]
                        entry = (-rank, row_sequence, record)
                        if len(heap) < quota:
                            heapq.heappush(heap, entry)
                        elif rank < -heap[0][0]:
                            heapq.heapreplace(heap, entry)

        archive_summaries.append(
            {
                "archive_filename": source["filename"],
                "source_url": source["url"],
                "archive_sha256": sha256_file(path),
                "archive_bytes": path.stat().st_size,
                "archive_retrieved_at_utc": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
                "csv_member": member.filename,
                "source_columns": source_columns,
                "source_rows": source_rows,
                "earliest_received_date": earliest.strftime("%Y-%m-%d") if earliest is not None else None,
                "latest_received_date": latest.strftime("%Y-%m-%d") if latest is not None else None,
                "missing_values_by_field": {
                    column: int(missing_counts[column]) for column in SOURCE_FIELDS if column in source_columns
                },
                "narrative_eligible_rows": int(sum(source_eligible_by_month.values())),
                "narrative_eligible_rows_by_month": dict(sorted(source_eligible_by_month.items())),
                "source_rows_by_month": dict(sorted(source_month_counts.items())),
            }
        )

    sampled_records: list[dict[str, str]] = []
    selected_count_by_split = {}
    for split_name, heap in heaps.items():
        entries = sorted(heap, key=lambda entry: (-entry[0], entry[1]))
        selected_count_by_split[split_name] = len(entries)
        for _, _, (date_text, label, narrative, archive_filename, complaint_id) in entries:
            sampled_records.append(
                {
                    "Date received": date_text,
                    "Issue": label,
                    "Consumer complaint narrative": narrative,
                    "split": split_name,
                    "source_archive": archive_filename,
                    "Complaint ID": complaint_id,
                }
            )
    sample = pd.DataFrame(sampled_records)
    if sample.empty:
        raise ValueError("No usable narratives were found in the selected CFPB archive exports.")
    sample["Date received"] = pd.to_datetime(sample["Date received"], errors="raise")
    sample = sample.sort_values(["Date received", "Issue", "source_archive"]).reset_index(drop=True)

    source_taxonomy_by_year = {
        year: sorted(labels) for year, labels in sorted(all_issue_labels_by_year.items())
    }
    eligible_taxonomy_by_year = {
        year: sorted(labels.keys())
        for year, labels in sorted(eligible_issue_counts_by_year.items())
    }
    taxonomy_changes = {}
    previous_labels: set[str] = set()
    for year, labels in eligible_taxonomy_by_year.items():
        current_labels = set(labels)
        taxonomy_changes[year] = {
            "category_count": len(labels),
            "new_vs_prior_observed_year": sorted(current_labels - previous_labels),
            "no_longer_observed_vs_prior_observed_year": sorted(previous_labels - current_labels),
        }
        previous_labels = current_labels

    metadata: dict[str, Any] = {
        "source_page": ARCHIVE_PAGE,
        "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sample_seed": SAMPLE_SEED,
        "sample_limit": max_rows,
        "sample_quotas": quotas,
        "sample_selected_before_duplicate_removal": selected_count_by_split,
        "split_periods": SPLIT_PERIODS,
        "eligible_rows_by_split_in_selected_exports": {
            split_name: int(split_eligible_counts[split_name]) for split_name in SPLIT_PERIODS
        },
        "narrative_eligible_rows_by_month": dict(sorted(eligible_month_counts.items())),
        "source_rows_by_month": dict(sorted(all_month_counts.items())),
        "archive_summaries": archive_summaries,
        "source_taxonomy_by_year": source_taxonomy_by_year,
        "narrative_eligible_taxonomy_by_year": eligible_taxonomy_by_year,
        "taxonomy_changes_by_year": taxonomy_changes,
        "source_rows_scanned": int(sum(item["source_rows"] for item in archive_summaries)),
        "narrative_eligible_rows_scanned": int(sum(
            item["narrative_eligible_rows"] for item in archive_summaries
        )),
        "narrative_eligible_date_coverage": {
            "earliest": min(
                min(item["narrative_eligible_rows_by_month"])
                for item in archive_summaries
                if item["narrative_eligible_rows_by_month"]
            ),
            "latest": max(
                max(item["narrative_eligible_rows_by_month"])
                for item in archive_summaries
                if item["narrative_eligible_rows_by_month"]
            ),
        },
        "source_date_coverage": {
            "earliest": min(
                item["earliest_received_date"]
                for item in archive_summaries
                if item["earliest_received_date"] is not None
            ),
            "latest": max(
                item["latest_received_date"]
                for item in archive_summaries
                if item["latest_received_date"] is not None
            ),
        },
        "sampling_method": (
            "Per-split deterministic bottom-hash sample keyed by CFPB Complaint ID; "
            "60% train, 20% validation, 20% final test; capped at 100,000 rows."
        ),
        "narrative_eligibility_rule": (
            "Nonblank Consumer complaint narrative, nonblank Issue, valid Date received, "
            "and nonblank Complaint ID."
        ),
        "complaint_ids_persisted": False,
    }
    return sample, metadata


def remove_duplicate_leakage(sample: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = sample.copy()
    if "Complaint ID" not in frame.columns:
        raise ValueError("Complaint ID is required for duplicate-leakage checks.")
    frame["Complaint ID"] = frame["Complaint ID"].astype(str)
    frame["normalized_narrative"] = frame["Consumer complaint narrative"].map(normalize_narrative)
    frame["narrative_sha256"] = frame["normalized_narrative"].map(
        lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    )
    duplicate_id_rows = int(frame["Complaint ID"].duplicated(keep="first").sum())
    duplicate_ids_across_splits = int(
        (frame.groupby("Complaint ID")["split"].nunique() > 1).sum()
    )
    cross_split_text_groups = int(
        (frame.groupby("narrative_sha256")["split"].nunique() > 1).sum()
    )
    duplicate_text_rows = int(frame["narrative_sha256"].duplicated(keep="first").sum())
    frame = frame.sort_values(["Date received", "Complaint ID", "narrative_sha256"])
    frame = frame.drop_duplicates("Complaint ID", keep="first")
    frame = frame.drop_duplicates("narrative_sha256", keep="first")
    leakage_remaining = int(
        (frame.groupby("narrative_sha256")["split"].nunique() > 1).sum()
    )
    if leakage_remaining:
        raise AssertionError("Exact duplicate narrative leakage remains across temporal splits.")
    frame = frame.drop(columns=["Complaint ID", "normalized_narrative", "narrative_sha256"])
    frame = frame.sort_values(["Date received", "Issue"]).reset_index(drop=True)
    return frame, {
        "sample_duplicate_complaint_id_rows_before_removal": duplicate_id_rows,
        "complaint_ids_crossing_temporal_splits_before_removal": duplicate_ids_across_splits,
        "exact_normalized_duplicate_narrative_rows_before_removal": duplicate_text_rows,
        "exact_duplicate_text_groups_crossing_splits_before_removal": cross_split_text_groups,
        "duplicate_rows_removed": int(len(sample) - len(frame)),
        "sample_rows_after_duplicate_removal": int(len(frame)),
        "exact_duplicate_text_groups_crossing_splits_after_removal": leakage_remaining,
        "duplicate_policy": (
            "Normalize Unicode/case and whitespace; for duplicate complaint IDs or exact normalized "
            "narratives, retain only the earliest received-date row. This prevents exact text or ID "
            "from crossing train/validation/test."
        ),
    }


def _simhash_word_trigrams(text: str) -> int | None:
    tokens = re.findall(r"\w+", normalize_narrative(text), flags=re.UNICODE)
    if len(tokens) < 4:
        return None
    shingles = {
        " ".join(tokens[index : index + 3])
        for index in range(len(tokens) - 2)
    }
    hashes = np.fromiter(
        (
            int.from_bytes(
                hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest(),
                "big",
            )
            for shingle in shingles
        ),
        dtype=np.uint64,
        count=len(shingles),
    )
    bit_matrix = np.unpackbits(
        hashes.astype(">u8", copy=False).view(np.uint8).reshape(-1, 8),
        axis=1,
    )
    packed = np.packbits(bit_matrix.sum(axis=0) * 2 >= len(hashes))
    return int.from_bytes(packed.tobytes(), "big")


def remove_near_duplicate_leakage(
    sample: pd.DataFrame,
    max_hamming_distance: int = 3,
    max_bucket_size: int = 150,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    signatures = [
        _simhash_word_trigrams(text)
        for text in sample["Consumer complaint narrative"].astype(str)
    ]
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for row_index, signature in enumerate(signatures):
        if signature is None:
            continue
        for band in range(4):
            band_value = (signature >> (band * 16)) & 0xFFFF
            buckets[(band, band_value)].append(row_index)

    candidate_pairs: set[tuple[int, int]] = set()
    skipped_oversized_buckets = 0
    for members in buckets.values():
        if len(members) > max_bucket_size:
            skipped_oversized_buckets += 1
            continue
        if len(members) < 2:
            continue
        for left_position, left in enumerate(members[:-1]):
            for right in members[left_position + 1 :]:
                if sample.iloc[left]["split"] == sample.iloc[right]["split"]:
                    continue
                candidate_pairs.add((min(left, right), max(left, right)))

    duplicate_pairs = []
    removed_indices: set[int] = set()
    for left, right in candidate_pairs:
        left_signature = signatures[left]
        right_signature = signatures[right]
        if left_signature is None or right_signature is None:
            continue
        distance = (left_signature ^ right_signature).bit_count()
        if distance <= max_hamming_distance:
            duplicate_pairs.append((left, right, distance))
            left_date = pd.Timestamp(sample.iloc[left]["Date received"])
            right_date = pd.Timestamp(sample.iloc[right]["Date received"])
            if left_date < right_date:
                removed_indices.add(right)
            elif right_date < left_date:
                removed_indices.add(left)
            else:
                removed_indices.add(right)

    kept_indices = [
        row_index for row_index in range(len(sample)) if row_index not in removed_indices
    ]
    filtered = sample.iloc[kept_indices].reset_index(drop=True)
    remaining_signatures = [signatures[row_index] for row_index in kept_indices]
    remaining_splits = filtered["split"].tolist()
    remaining_buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for row_index, signature in enumerate(remaining_signatures):
        if signature is None:
            continue
        for band in range(4):
            remaining_buckets[
                (band, (signature >> (band * 16)) & 0xFFFF)
            ].append(row_index)
    remaining_cross_split_pairs: set[tuple[int, int]] = set()
    remaining_oversized_buckets = 0
    for members in remaining_buckets.values():
        if len(members) > max_bucket_size:
            remaining_oversized_buckets += 1
            continue
        for left_position, left in enumerate(members[:-1]):
            for right in members[left_position + 1 :]:
                if remaining_splits[left] == remaining_splits[right]:
                    continue
                left_signature = remaining_signatures[left]
                right_signature = remaining_signatures[right]
                if (
                    left_signature is not None
                    and right_signature is not None
                    and (left_signature ^ right_signature).bit_count()
                    <= max_hamming_distance
                ):
                    remaining_cross_split_pairs.add((min(left, right), max(left, right)))

    return filtered, {
        "near_duplicate_method": (
            "Deterministic 64-bit SimHash over unique word trigrams; four 16-bit locality-sensitive "
            "bands generate candidates; verify at Hamming distance <= 3. Cross-split later records "
            "are removed. Narratives with fewer than four words are skipped."
        ),
        "near_duplicate_max_hamming_distance": max_hamming_distance,
        "near_duplicate_bucket_size_cap": max_bucket_size,
        "near_duplicate_candidate_pairs_checked": len(candidate_pairs),
        "near_duplicate_pairs_across_splits_removed": len(duplicate_pairs),
        "near_duplicate_rows_removed": len(removed_indices),
        "near_duplicate_oversized_buckets_skipped": skipped_oversized_buckets,
        "cross_split_near_duplicate_pairs_remaining_in_checked_buckets": len(remaining_cross_split_pairs),
        "remaining_oversized_buckets_skipped": remaining_oversized_buckets,
        "near_duplicate_check_is_approximate": True,
    }


def select_training_taxonomy(
    train_labels: pd.Series,
    top_k: int = TOP_TRAIN_LABELS,
    minimum_support: int = MIN_TRAIN_LABEL_SUPPORT,
) -> dict[str, Any]:
    counts = train_labels.value_counts()
    selected = [
        str(label)
        for label, count in counts.items()
        if int(count) >= minimum_support
    ][:top_k]
    if len(selected) < 2:
        raise ValueError("Training data has fewer than two adequately supported Issue labels.")
    return {
        "selected_issue_labels": selected,
        "other_label": OTHER_LABEL,
        "selection_rule": (
            f"Top {top_k} Issue labels by training-sample frequency with at least "
            f"{minimum_support} training examples; all other source labels map to Other."
        ),
        "source_label_counts_in_train": {str(k): int(v) for k, v in counts.items()},
    }


def map_issue_labels(labels: pd.Series, selected_labels: list[str]) -> pd.Series:
    selected = set(selected_labels)
    return labels.map(lambda label: label if label in selected else OTHER_LABEL)


def _evaluate(
    y_true: pd.Series,
    y_pred: np.ndarray,
    labels: list[str],
) -> dict[str, Any]:
    return {
        "rows": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
        "per_class": classification_report(
            y_true,
            y_pred,
            labels=labels,
            target_names=labels,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": {
            "labels": labels,
            "counts": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        },
    }


def train_and_evaluate(
    sample: pd.DataFrame,
    provenance: dict[str, Any],
    model_path: Path = MODEL_PATH,
) -> dict[str, Any]:
    splits = {name: sample[sample["split"] == name].copy() for name in SPLIT_PERIODS}
    for name, split in splits.items():
        if split.empty:
            raise ValueError(f"No records available for the {name} split.")
    if not (
        splits["train"]["Date received"].max()
        < splits["validation"]["Date received"].min()
        < splits["test"]["Date received"].min()
    ):
        raise ValueError("Train, validation, and test periods are not strictly chronological.")

    taxonomy = select_training_taxonomy(splits["train"]["Issue"])
    selected_labels = taxonomy["selected_issue_labels"]
    y_by_split = {
        name: map_issue_labels(split["Issue"], selected_labels)
        for name, split in splits.items()
    }
    class_labels = sorted(y_by_split["train"].unique().tolist())
    X_train = splits["train"]["Consumer complaint narrative"]
    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(np.zeros((len(X_train), 1)), y_by_split["train"])
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        max_features=100_000,
        sublinear_tf=True,
        dtype=np.float32,
    )
    model = Pipeline(
        [
            ("tfidf", vectorizer),
            (
                "classifier",
                OneVsRestClassifier(
                    LogisticRegression(
                        C=2.0,
                        class_weight="balanced",
                        solver="liblinear",
                        max_iter=400,
                        tol=1e-3,
                        random_state=SAMPLE_SEED,
                    ),
                    n_jobs=1,
                ),
            ),
        ]
    )
    started = time.perf_counter()
    model.fit(X_train, y_by_split["train"])
    train_seconds = time.perf_counter() - started

    results: dict[str, Any] = {
        "source_page": ARCHIVE_PAGE,
        "model_type": "TF-IDF word unigrams/bigrams + class-weighted logistic regression",
        "empirical_modeling_status": "completed for archived narratives only",
        "training_scope": (
            "Archived CFPB complaint narratives in selected official exports only. "
            "Not evaluated on current post-archive structured complaints."
        ),
        "feature_configuration": {
            "ngram_range": [1, 2],
            "min_df": 2,
            "max_features": 100_000,
            "sublinear_tf": True,
            "logistic_regression_C": 2.0,
            "class_weight": "balanced",
            "solver": "liblinear (one-vs-rest for multiclass)",
            "max_iter": 400,
            "confidence_scores": "Uncalibrated predict_proba scores; not operational confidence.",
        },
        "taxonomy": taxonomy,
        "split_periods": provenance["split_periods"],
        "sampled_rows_by_split": {
            name: int(len(splits[name])) for name in SPLIT_PERIODS
        },
        "deduplicated_rows_by_split": {
            name: int(len(splits[name])) for name in SPLIT_PERIODS
        },
        "source_label_distribution_by_split": {
            name: {str(k): int(v) for k, v in splits[name]["Issue"].value_counts().items()}
            for name in SPLIT_PERIODS
        },
        "mapped_label_distribution_by_split": {
            name: {str(k): int(v) for k, v in y_by_split[name].value_counts().items()}
            for name in SPLIT_PERIODS
        },
        "unseen_issue_label_rows_mapped_to_other": {
            name: int((~splits[name]["Issue"].isin(selected_labels)).sum())
            for name in SPLIT_PERIODS
        },
        "training_duration_seconds": round(train_seconds, 3),
        "vocabulary_size": int(len(model.named_steps["tfidf"].vocabulary_)),
        "evaluation": {},
        "limitation": (
            "The archive exports sampled for modeling are discontinuous: 2011-12–2018-04, "
            "2025-11–2025-12, and 2026-01–2026-08. Observed eligible narratives in the oldest "
            "batch begin in 2015. The final test is a temporal transfer across a multi-year gap."
        ),
        "source_provenance": provenance,
    }
    for split_name in ("validation", "test"):
        X_eval = splits[split_name]["Consumer complaint narrative"]
        baseline_pred = baseline.predict(np.zeros((len(X_eval), 1)))
        model_pred = model.predict(X_eval)
        results["evaluation"][split_name] = {
            "baseline_most_frequent": _evaluate(
                y_by_split[split_name], baseline_pred, class_labels
            ),
            "tfidf_logistic_regression": _evaluate(
                y_by_split[split_name], model_pred, class_labels
            ),
        }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path, compress=3)
    return results


def run(
    refresh_archives: bool = False,
    max_rows: int = SAMPLE_LIMIT,
    fit_model: bool = True,
) -> dict[str, Any]:
    local_sources = download_archives(refresh=refresh_archives)
    sample, provenance = collect_archived_sample(local_sources, max_rows=max_rows)
    sample, duplicate_summary = remove_duplicate_leakage(sample)
    sample, near_duplicate_summary = remove_near_duplicate_leakage(sample)
    duplicate_summary.update(near_duplicate_summary)
    provenance["sampled_rows_by_split_after_deduplication"] = {
        split: int(count) for split, count in sample["split"].value_counts().items()
    }
    provenance["duplicate_leakage_checks"] = duplicate_summary
    provenance["sampled_narrative_missingness"] = {
        "blank_narrative_rows": int(
            sample["Consumer complaint narrative"].fillna("").str.strip().eq("").sum()
        ),
        "blank_issue_rows": int(sample["Issue"].fillna("").str.strip().eq("").sum()),
        "invalid_date_rows": int(pd.to_datetime(sample["Date received"], errors="coerce").isna().sum()),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample.to_parquet(SAMPLE_PATH, index=False)
    SAMPLE_METADATA_PATH.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    manifest = {
        "source": ARCHIVE_PAGE,
        "retrieval_method": (
            "Official CFPB Narrative Archive ZIP exports downloaded locally and read in CSV chunks."
        ),
        "retrieval_timestamp_utc": provenance["retrieval_timestamp_utc"],
        "query_parameters": {"date_filters": None, "row_limit": None},
        "export_coverage": provenance["source_date_coverage"],
        "archive_files": provenance["archive_summaries"],
        "source_rows_scanned": provenance["source_rows_scanned"],
        "narrative_eligible_rows_scanned": provenance["narrative_eligible_rows_scanned"],
        "narrative_eligible_rows_by_month": provenance["narrative_eligible_rows_by_month"],
        "source_taxonomy_by_year": provenance["source_taxonomy_by_year"],
        "narrative_eligible_taxonomy_by_year": provenance["narrative_eligible_taxonomy_by_year"],
        "taxonomy_changes_by_year": provenance["taxonomy_changes_by_year"],
        "sample_rows": int(len(sample)),
        "sample_rows_by_split": provenance["sampled_rows_by_split_after_deduplication"],
        "split_periods": provenance["split_periods"],
        "narrative_modeling_status": (
            "Empirical modeling is complete for the selected archived CFPB narratives. "
            "This does not represent current post-archive narratives."
        ),
        "duplicate_leakage_checks": duplicate_summary,
        "sampling_method": provenance["sampling_method"],
        "narrative_eligibility_rule": provenance["narrative_eligibility_rule"],
        "complaint_ids_persisted": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not fit_model:
        return manifest

    metrics = train_and_evaluate(sample, provenance)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    manifest["model_metrics_path"] = str(METRICS_PATH.relative_to(PROJECT_DIR))
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = {
        "source_rows_scanned": provenance["source_rows_scanned"],
        "eligible_narratives_scanned": provenance["narrative_eligible_rows_scanned"],
        "sample_rows_after_deduplication": len(sample),
        "sample_rows_by_split": provenance["sampled_rows_by_split_after_deduplication"],
        "duplicate_leakage_checks": duplicate_summary,
        "test_baseline": metrics["evaluation"]["test"]["baseline_most_frequent"],
        "test_model": metrics["evaluation"]["test"]["tfidf_logistic_regression"],
        "model_path": str(MODEL_PATH),
        "metrics_path": str(METRICS_PATH),
    }
    print(json.dumps(result, indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and evaluate a local CFPB archived-narrative classifier."
    )
    parser.add_argument("--refresh-archives", action="store_true")
    parser.add_argument("--max-rows", type=int, default=SAMPLE_LIMIT)
    parser.add_argument("--scan-only", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run(
        refresh_archives=arguments.refresh_archives,
        max_rows=arguments.max_rows,
        fit_model=not arguments.scan_only,
    )

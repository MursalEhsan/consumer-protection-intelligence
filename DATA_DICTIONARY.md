# Data Dictionary and Quality Summary

## Source

Official [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/). CFPB generally updates the source daily. Complaints sent to companies for response are published after company response and confirmation of a commercial relationship, or after 15 days, whichever comes first. The CFPB cautions that the database is not representative of all marketplace experiences.

The current public Consumer Complaint Database does not include complaint narratives. CFPB's official release notes state that narratives were removed. A separate official CFPB Narratives Archive is used by the local historical text-classification workflow; it is not part of the structured trend dataset.

## Source fields

| Field | Meaning | Project use |
|---|---|---|
| `Date received` | Date the complaint was received | Full-source monthly aggregation; sample |
| `Product` | Product category | Sample only |
| `Sub-product` | Product subcategory | Sample only |
| `Issue` | Operational CFPB complaint category | Full-source monthly aggregation; sample |
| `Sub-issue` | More specific operational issue | Missingness/schema audit only |
| `Complaint ID` | Source record identifier | Deterministic sampling and sample duplicate check; dropped before persistence |
| `Submitted via` | Consumer submission channel | Sample only |
| `Company`, `State`, `ZIP code`, `Tags` | Company, geographic, and context fields | Missingness audit only; excluded from persisted sample |
| Response and date fields | Company response and complaint handling | Missingness/schema audit only; excluded from persisted sample |

The complete source schema is recorded in `CFPB_DATA_MANIFEST.json`.

## Separate archived narrative model

The official CFPB Narratives Archive exports are processed separately. Eligible records require nonblank `Consumer complaint narrative`, `Issue`, and `Complaint ID`, plus a valid `Date received`. Complaint IDs support deterministic sampling and duplicate checks, then are removed before the sample is persisted. The local sample and trained model are generated under ignored local output paths; archive provenance, coverage, missingness, taxonomy changes, and evaluation are recorded in `CFPB_NARRATIVE_MODEL_MANIFEST.json` and `output/cfpb_narrative_model_metrics.json`.

The archive's selected exports are discontinuous. The classifier uses train dates through 2025-10, validation in 2025-11–12, and a final test through 2026-08-14. These dates must not be conflated with later current structured-data coverage.

## Derived tables and columns

### `complaint_sample`

At most 100,000 deterministic sample records, stored locally without Complaint ID. Includes `Date received`, `Product`, `Sub-product`, `Issue`, and `Submitted via`.

### `source_monthly_issue_counts`

- `month`: calendar month of `Date received` (`YYYY-MM`)
- `issue`: operational issue value; missing values are represented as `Unknown`
- `count`: full-source number of records in that month and issue group

### `source_monthly_totals`

- `month`: calendar month of `Date received` (`YYYY-MM`)
- `complaint_count`: full-source number of records with a valid received date in that month

### `vw_monthly_issue_trends`

- `complaint_month`: month key
- `issue`: operational issue value
- `complaint_count`: full-source issue count for the month
- `monthly_denominator`: all full-source records with a valid received date in the month
- `complaint_share`: issue count divided by that month’s denominator

## Sampling and data minimization

The archive is streamed in 200,000-row chunks. A deterministic 1-in-100 hash sample keyed by Complaint ID is uniformly capped at 100,000 rows. IDs are removed before the sample is written to Parquet or SQLite. Exact monthly aggregates are generated from the full scan; the sample is not used as the monthly denominator.

The SHA-256 checksum, retrieval time, full row count, date coverage, checked-field missingness counts, sample size, and monthly aggregates are written to `CFPB_DATA_MANIFEST.json` and local outputs.

## Quality and interpretation

- Full-source missing-value counts for fields present in the archive
- Usable date coverage and invalid/missing-date counts
- Duplicate Complaint ID count in the temporary sample before IDs are dropped
- Sample-level missingness and date range
- Current structured schema and narrative-column candidate check
- Conservative 15-day publication maturity cutoff for monthly trends

Complaint counts are not estimates of market-wide harm or incident prevalence. Source `Issue` categories are operational labels, not adjudicated outcomes. The separate archived classifier is a historical baseline, not a current or continuously updated text model.

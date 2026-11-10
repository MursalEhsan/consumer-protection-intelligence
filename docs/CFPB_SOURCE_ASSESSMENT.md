# CFPB Source Assessment

## Result

The current official CFPB Consumer Complaint Database is accessible for local, structured aggregate analysis, but has no narrative field. CFPB's [API release notes](https://cfpb.github.io/api/ccdb/release-notes.html) state that narratives were removed from that database.

A separate official [CFPB Consumer Complaint Database Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/) was inspected. The downloaded archive exports contain usable narrative, Issue, Complaint ID, and received-date fields. The selected exports support a bounded historical classifier, but are discontinuous and must not be confused with the current structured source. Measured archive coverage, missingness, taxonomy changes, and model metrics are recorded in `CFPB_NARRATIVE_MODEL_MANIFEST.json` and `output/cfpb_narrative_model_metrics.json`.

## Verified source and method

- Source: [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/)
- Bulk archive: `https://files.consumerfinance.gov/ccdb/complaints.csv.zip`
- Retrieval method: download the official ZIP locally; hash it with SHA-256; inspect the CSV header; stream the full CSV in 200,000-row chunks.
- Maximum persisted sample: 100,000 rows, deterministically selected using a 1-in-100 hash of Complaint ID and uniformly capped if necessary. Complaint IDs are removed before persistence.
- Full-source monthly issue totals and monthly denominators are computed during the complete archive scan, not from the capped sample.
- The exact snapshot checksum, retrieval timestamp, row count, date coverage, checked-field missingness, and monthly counts are recorded in `CFPB_DATA_MANIFEST.json`.

The prior full-archive inspection covered 19,020,152 rows from 2011-12-01 through 2026-11-08. A separate local review run later scanned 19,028,339 rows through 2026-11-09; its ignored manifest and dated aggregate report record those results. Rerunning `make run` refreshes generated metadata from the archive present locally. The generated manifest is the record of truth for a given run.

## Separate archived narrative source

- Source: official [CFPB Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/), not the current bulk archive or API.
- Verified fields: `Consumer complaint narrative`, `Issue`, `Date received`, and `Complaint ID`.
- Selected archive exports: 11,917,416 source rows, with 1,789,934 rows meeting the nonblank narrative/Issue/ID and valid-date eligibility rule. These are counts in the selected exports, not a continuous record of all narratives.
- Available export coverage is discontinuous: 2011-12 through 2018-04 and 2024-11 onward. The model uses only 2024-11 through 2026-08-14 for chronological train/validation/test evaluation; selected exports in the earlier period support archive provenance and taxonomy review, not the model split.
- The August 2026 export is listed through August 14 on the archive page, but inspection found only one eligible narrative in that export; page-level coverage must not be mistaken for usable narrative density.
- Complaint IDs are used locally for deterministic sampling and duplicate checks, then removed before sample persistence. Narratives remain local and are present only in ignored outputs.
- Source `Issue` labels are operational categories. The classifier selects a top-label taxonomy from training data only and maps unselected labels to an Other class.
- The model is not evaluated on post-archive narratives and is not continuously updated. Current structured-data trend coverage is reported separately in `CFPB_DATA_MANIFEST.json`.

The archive data support a real historical baseline, not a claim about current complaint narratives. See the model card and metrics artifact for the exact evaluation and limitations.

## Publication and interpretation limits

CFPB generally updates the database daily. Complaints sent to companies for response are published after the company responds and confirms a commercial relationship, or after 15 days, whichever comes first. The archive has no per-record public release timestamp, so a gap from receipt date to retrieval date is not a measured publication lag.

CFPB cautions that complaint data are not representative of all consumer marketplace experiences. Counts describe published complaints only; they are not estimates of prevalence or verified incidents. `Issue` values are operational source categories, not adjudicated ground truth. Recent months are excluded from trend analysis until a conservative 15-day maturity cutoff is met.

## Refresh

```bash
make run
```

Force a fresh public archive download and rescan:

```bash
make refresh-data
```

Rebuild the separate historical narrative sample, model, and chronological evaluation:

```bash
make narrative-model
```

The pipelines are local-only after permitted public-source retrieval. They do not publish or deploy outputs, upload complaint data, or invoke an external LLM.

# Technical Report

## Scope and source separation

The project contains two CFPB workflows that must not be conflated:

- The current Consumer Complaint Database pipeline analyzes structured metadata and issue counts. The current schema has no narrative field.
- A separate historical narrative model uses selected ZIP exports from the official CFPB Narratives Archive.

The narrative archive exports were inspected for real complaint narratives, Issue labels, complaint IDs, and received dates. Selected exports cover 2011-12 through 2018-04 and 2024-11 through 2026-08, with a large gap between. Only the recent portion is used for model training and chronological validation/testing. The archive page's stated coverage is not equivalent to usable narrative coverage in every export; actual source counts, dates, missingness, and yearly taxonomy changes are recorded in the narrative manifest.

## Narrative sample and leakage controls

Eligible records have nonblank narrative, nonblank `Issue`, valid received date, and nonblank Complaint ID. The deterministic per-period sample is capped at 100,000 rows before duplicate filtering. Complaint IDs are used for sampling and duplicate checks, then removed before sample persistence.

Exact normalized narratives and duplicate complaint IDs are removed, retaining the earliest record. A bounded SimHash check over word trigrams then detects high-similarity candidates across temporal splits; it is approximate and skips oversized candidate buckets and narratives shorter than four words. The manifest records the filter counts and skipped-bucket limitations. This is a practical leakage control, not a proof that all semantically similar text has been removed.

## Narrative model and evaluation

The model is TF-IDF word unigrams/bigrams followed by class-weighted one-vs-rest logistic regression. The comparison baseline predicts the most frequent training class. The split is chronological:

| Partition | Received dates |
|---|---|
| Train | 2024-11-01 through 2025-10-31 |
| Validation | 2025-11-01 through 2025-12-31 |
| Final test | 2026-01-01 through 2026-08-14 |

The selected taxonomy is derived only from the training labels; other source Issue categories map to an Other class. Metrics, class distributions, per-class results, and confusion matrices are in `output/cfpb_narrative_model_metrics.json`. The final test is a temporal transfer after the training period, not an independent random sample. It has not been used to claim performance on complaints after August 14, 2026.

The source `Issue` target is operational, not adjudicated ground truth. No human label audit was performed. The Other class combines heterogeneous out-of-taxonomy issues. Reported prediction scores are uncalibrated. The model is a baseline and is not approved for operational decisions.

## Current structured-data trend pipeline

The separate structured pipeline downloads the official current bulk archive when needed, records its checksum and retrieval time, streams it in chunks, and computes monthly issue counts and denominators over all valid-date records. A deterministic sample of at most 100,000 rows is stored locally without complaint IDs. Trend months are excluded until the entire calendar month meets a conservative 15-day publication-maturity cutoff.

For each issue and calendar month, the exploratory candidate rule compares with up to five prior observations of the same calendar month. It requires at least three historical observations and 50 current complaints, flagging increases of three or more historical standard deviations. This screening heuristic is not a validated hypothesis test or incident detector.

## Interpretation and privacy boundaries

The classifier's historical text coverage ends at 2026-08-14. Current structured trend data may extend later, but do not infer text-model coverage, validation, or refresh from those later structured dates. The selected narrative archive batches are discontinuous and may have uneven narrative missingness and evolving Issue taxonomy.

CFPB cautions that complaint data are not representative of all marketplace experiences. Counts and shares cannot establish market-wide prevalence, causation, wrongdoing, or resolution. Both workflows remain local-only; the dashboard inference form does not write entered text to project data or model artifacts.

## Reproduction

```bash
make narrative-model
make test
make run
make report
make app
```

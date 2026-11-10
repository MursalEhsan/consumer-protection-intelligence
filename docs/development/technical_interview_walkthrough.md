# Technical Interview Walkthrough

## 1. Task and separate sources

The current structured CFPB database contains no narrative field. The separate official CFPB Narratives Archive contains actual narratives with Issue labels, complaint IDs, and received dates. A TF-IDF/logistic-regression baseline was trained and evaluated only on selected archived narratives; it is not evaluated on later text or current structured records.

## 2. Current structured-data pipeline

The pipeline records the public archive hash and retrieval time, scans it in chunks, and computes monthly counts across the full archive. A deterministic sample of at most 100,000 rows is stored locally for SQL exploration; complaint IDs are removed before persistence. Monthly issue shares use all valid-date records as denominators.

## 3. Archived narrative model

Selected exports are discontinuous, and only the recent archive period is used for model splits: train through 2025-10, validation in 2025-11–12, and held-out test through 2026-08-14. The deterministic capped sample is checked for duplicate complaint IDs and exact text leakage; approximate SimHash candidates remove near-identical cross-split records. A training-derived Issue taxonomy maps unselected categories to Other. Evaluation compares against a majority baseline.

## 4. Maturity and alerting

The trend output excludes months until the full calendar month satisfies a conservative 15-day publication cutoff. The exploratory alert compares issue share to prior observations of the same calendar month and applies minimum-history, minimum-count, and standard-deviation thresholds. These are review prompts, not validated incident alerts.

## 5. Measurement and guardrails

On the 18,215-row final archive test, the TF-IDF/logistic-regression baseline attained 0.6294 accuracy, 0.3939 macro-F1, and 0.6236 weighted-F1; the training-majority baseline attained 0.0340 accuracy and 0.0060 macro-F1. About half the test maps to the heterogeneous Other class, so these metrics need per-class review. CFPB `Issue` labels are operational categories, not adjudicated ground truth. No human audit was run, and the CFPB warns the database is not representative of all marketplace experiences. Trend counts and shares cannot establish prevalence, causation, wrongdoing, or resolution.

The archived model has not undergone human label audit or post-archive evaluation. Its confidence-like scores are uncalibrated. Current structured trend dates do not extend model coverage.

## 6. Next validation needs

Conduct a human label-quality audit on a separately held-out sample before operational use. Any extension beyond 2026-08-14 requires a new authorized narrative source and a fresh chronological evaluation. Keep current structured trend analysis distinct from text predictions.

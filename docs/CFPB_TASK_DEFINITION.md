# CFPB Complaint Project: Task Definition

## Scope and status

The project has two distinct outputs:

1. **Current structured-data analysis:** full-source issue-count trends from the current public Consumer Complaint Database. Its schema has no narrative field.
2. **Historical narrative classification:** a local TF-IDF plus logistic-regression baseline using a selected, discontinuous set of official CFPB Narratives Archive exports.

The classifier trains on archive narratives received 2024-11 through 2025-10, validates on 2025-11 through 2025-12, and uses 2026-01 through 2026-08-14 as a chronological held-out test. It is not evaluated on later narratives, current structured data, or a continuously refreshed text dataset.

## Narrative source and unit

- Source: official [CFPB Consumer Complaint Database Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/)
- Unit: one eligible archived complaint with nonblank narrative, nonblank `Issue`, valid received date, and nonblank Complaint ID.
- Selected export provenance, coverage, missingness, and yearly taxonomy changes are recorded in the generated local `CFPB_NARRATIVE_MODEL_MANIFEST.json`, not committed.
- Sampling: deterministic by Complaint ID within chronological split, capped at 100,000 before duplicate removal.
- Duplicate controls: complaint-ID and exact normalized-text deduplication, plus approximate SimHash word-trigram checks for cross-split near duplicates.
- Target: `Issue` taxonomy selected from training labels only; all nonselected categories map to an explicit Other class.

## Modeling and evaluation

- Classifier: TF-IDF word unigrams/bigrams and class-weighted one-vs-rest logistic regression.
- Baseline: majority-class dummy classifier.
- Validation and final test are chronological and held out from fitting. Reported metrics include accuracy, macro-F1, weighted-F1, per-class results, and confusion matrices.
- Exact final evaluation values and caveats are reported in the committed [`EVALUATION_AUDIT.md`](../EVALUATION_AUDIT.md); generated metrics JSON is local-only. Do not quote values from pre-dedup runs or stale artifacts.
- Input-score outputs are uncalibrated. The model is a baseline, not a production decision system.

## Structured trend outputs

The separate current-data pipeline computes full-source monthly issue totals and shares, excluding recent months until the conservative 15-day publication-maturity cutoff. Exploratory same-calendar-month candidates are prompts for analyst review only, not confirmed incidents, causal findings, or prevalence estimates.

## Coverage and interpretation constraints

Selected narrative archive exports are discontinuous: 2011-12 through 2018-04 and 2024-11 through 2026-08. Modeling uses only the recent portion, with a large gap before that. The archive page’s listed coverage does not guarantee usable narratives in each export; the August 2026 export contained only one eligible narrative on inspection. Consult the manifest for actual row-level coverage and missingness.

Current structured trends extend beyond the narrative model’s cutoff. Their coverage dates do not extend the text model’s training or evaluation. CFPB complaint data are not representative of all marketplace experiences; `Issue` labels are operational categories, not adjudicated ground truth. The Other class is substantial and represents a mixture of out-of-taxonomy labels, not one semantic complaint type.

## Reproduction

```bash
make narrative-model
make test
make run
make report
make app
```

All processing is local after retrieval from official public CFPB pages. No data are uploaded, and nothing is published or deployed.

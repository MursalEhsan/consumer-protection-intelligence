# Model Card: Historical CFPB Narrative Issue Baseline

## Status

A TF-IDF/logistic-regression baseline has been trained and evaluated on selected official CFPB Narratives Archive exports. It is local-only and not a production or continuously updated classifier. Current structured-data trend analysis is a separate workflow; its later coverage does not extend this model's text coverage.

## Intended use

- Demonstrate a reproducible historical text-classification baseline against CFPB archive `Issue` labels.
- Explore local predictions with non-sensitive, authorized text.
- Support research and evaluation only.

Do not use for legal, enforcement, credit, consumer eligibility, or company-ranking decisions. The source labels are operational categories, not adjudicated ground truth.

## Data and coverage

- Source: official [CFPB Consumer Complaint Database Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/).
- Selected exports scanned: 11,917,416 rows; 1,789,934 met the nonblank narrative/Issue/Complaint ID and valid-date eligibility rule.
- Selected export batches are discontinuous: 2011-12 through 2018-04, then 2024-11 through 2026-08. The archive page's coverage does not imply usable narrative density in every batch; the August 2026 export contained one eligible narrative.
- Model partitions: train 2024-11-01–2025-10-31; validation 2025-11-01–2025-12-31; final test 2026-01-01–2026-08-14.
- The current structured-data snapshot in `CFPB_DATA_MANIFEST.json` extends through received date 2026-11-08 (latest complete trend month 2026-09). That later structured coverage does not extend the narrative model's August 14, 2026 text cutoff.
- Sampling was capped at 100,000 before deduplication. Exact duplicate handling removed 28,813 rows; approximate near-duplicate handling removed another 660. Final partitions: 39,760 train, 12,552 validation, 18,215 test (70,527 total).
- Model taxonomy: top 10 Issue labels in the training sample, each with at least 100 examples; all other source categories map to `Other / outside selected training taxonomy`.
- Other-class support was 15.8% of training, 22.9% of validation, and 50.3% of test. This strong temporal label-distribution shift and heterogeneous catch-all materially limit interpretation.
- Complaint IDs support deterministic sampling and duplicate checks but are removed before the sample is persisted. Complaint text remains in ignored local outputs and is not uploaded.

Full archive file provenance, per-export counts and dates, checked-field missingness, yearly taxonomy changes, and duplicate-check details are in `CFPB_NARRATIVE_MODEL_MANIFEST.json`.

## Model

- Features: TF-IDF word unigrams and bigrams, minimum document frequency 2, maximum vocabulary 100,000, sublinear term frequency.
- Estimator: class-weighted one-vs-rest logistic regression (`C=2`, `liblinear`).
- Baseline: most-frequent class in training.
- Leakage controls: duplicate complaint IDs and exact normalized narratives are filtered, keeping the earliest record. A bounded 64-bit SimHash over unique word trigrams checks cross-split candidates at Hamming distance ≤3. Three oversized candidate buckets were skipped; zero matching pairs remained in checked buckets. This approximate method does not prove that all semantically similar narratives are absent.
- Evaluation: chronological validation and final test; accuracy, macro-F1, weighted-F1, per-class results, and confusion matrices are in `output/cfpb_narrative_model_metrics.json`.

## Results

| Split | Model | Accuracy | Macro-F1 | Weighted-F1 | Rows |
|---|---|---:|---:|---:|---:|
| Validation | Majority baseline | 0.3799 | 0.0501 | 0.2092 | 12,552 |
| Validation | TF-IDF + logistic regression | 0.6224 | 0.4603 | 0.6214 | 12,552 |
| Final test | Majority baseline | 0.0340 | 0.0060 | 0.0022 | 18,215 |
| Final test | TF-IDF + logistic regression | 0.6294 | 0.3939 | 0.6236 | 18,215 |

These are observed sample metrics, not guarantees of future performance. The test period has a major label-distribution shift; more than half of its rows map to Other, compared with about one-sixth of training. The very low test score of the training-majority baseline also reflects this temporal shift. Review the per-class metrics and confusion matrix rather than treating accuracy alone as evidence of broad classification quality.

## Limitations

- Not evaluated on complaints received after 2026-08-14, on later/current structured-data records, or on continuously updated text.
- The selected archive batches have a multi-year coverage gap. No claim is made about narratives absent from those exports or the current complaint database.
- The taxonomy is a training-sample-derived reduction of CFPB Issue categories. `Other` combines semantically diverse, often unseen categories and is not a single coherent issue.
- CFPB Issue is an operational complaint label, not a human-adjudicated narrative annotation. No blinded human label audit or inter-annotator study was performed.
- Current trends and archived text use different sources and coverage periods; do not merge their dates as if the classifier covered the structured pipeline's latest records.
- `predict_proba` values are uncalibrated model scores, not confidence guarantees.
- CFPB cautions that complaint data are not representative of all consumer marketplace experiences.

## Reproduction and artifacts

```bash
make narrative-model
make test
```

- Model: `complaint_narrative_tfidf_logreg.joblib` (local, ignored)
- Provenance: `CFPB_NARRATIVE_MODEL_MANIFEST.json`
- Evaluation: `output/cfpb_narrative_model_metrics.json`
- Dashboard: local archived-narrative tab in `src/streamlit_app.py`; submitted text is not written to the project dataset or model artifacts.

# Overnight Handoff

## Status

The archived-narrative classifier baseline has now been implemented, trained, and evaluated on verified CFPB archive exports. The existing current structured-data trend pipeline remains separate and in place. The model is a research baseline only; human label audit, post-archive evaluation, and operational deployment have not been done. Do not call it a continuously updated or current-text classifier.

This handoff records the completed implementation in the original working project; it is included here as technical documentation. This standalone copy has a fresh Git history and excludes raw exports, generated samples, and model binaries. The target GitHub repository was not confirmed private from unauthenticated access, so no remote is configured and nothing has been pushed, published, or deployed. Do not push until repository visibility is verified through the owner's authenticated GitHub account.

## Verified narrative archive evidence

- Official source: [CFPB Consumer Complaint Database Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/)
- Selected official ZIP exports scanned: **11,917,416 source rows**.
- Eligible rows with nonblank narrative, Issue, Complaint ID, and valid received date: **1,789,934**.
- Verified fields include `Consumer complaint narrative`, `Issue`, `Date received`, and `Complaint ID`.
- Selected exports are discontinuous: 2011-12 through 2018-04, then 2024-11 through 2026-08. The modeling period uses only the recent portion.
- The August 2026 export contained one eligible narrative despite the archive's page-level coverage statement. Page dates are not a proxy for row-level narrative availability.
- Per-export counts/dates, missingness, yearly taxonomy changes, and source records are in `CFPB_NARRATIVE_MODEL_MANIFEST.json`.

## Model and evaluation

- Deterministic sample cap: 100,000 before duplicate filtering.
- Exact duplicate rows removed: **28,813**. Approximate cross-split near-duplicate rows removed: **660**.
- Final sample: **70,527** — train 39,760; validation 12,552; test 18,215.
- Exact duplicate narrative groups crossing splits: **574 before** exact removal, **0 after**.
- Duplicate complaint IDs crossing splits: **0**.
- SimHash candidate pairs removed: **2,557**; 3 oversized buckets were skipped; no qualifying near-duplicate pairs remained in checked buckets. This approximate filter is not exhaustive.
- Chronological periods:
  - Train: 2024-11-01–2025-10-31
  - Validation: 2025-11-01–2025-12-31
  - Final test: 2026-01-01–2026-08-14
- Model: TF-IDF word unigrams/bigrams plus class-weighted one-vs-rest logistic regression. Baseline: most-frequent training class.
- Training-derived taxonomy: top 10 Issue labels with at least 100 train rows; other source labels map to `Other / outside selected training taxonomy`.
- Other-class support: **15.8% train**, **22.9% validation**, **50.3% test**, evidencing substantial temporal taxonomy/distribution shift.

| Split | Model | Accuracy | Macro-F1 | Weighted-F1 | Rows |
|---|---|---:|---:|---:|---:|
| Validation | Majority baseline | 0.3799 | 0.0501 | 0.2092 | 12,552 |
| Validation | TF-IDF + logistic regression | 0.6224 | 0.4603 | 0.6214 | 12,552 |
| Final test | Majority baseline | 0.0340 | 0.0060 | 0.0022 | 18,215 |
| Final test | TF-IDF + logistic regression | 0.6294 | 0.3939 | 0.6236 | 18,215 |

Interpret results cautiously: final-test label distribution shifts strongly; about half the test maps to the heterogeneous Other class. Source Issue is not adjudicated ground truth, no human label audit was done, and probability scores are uncalibrated. No performance is claimed for narratives after 2026-08-14. Current structured-data trends are a different source and may have later complaint dates.

For the currently recorded structured-data snapshot, received-date coverage extends through **2026-11-08** and the latest complete trend month is **2026-09**. Those structured dates are not narrative training or evaluation coverage.

## Code and generated artifacts

- `src/cfpb_narrative_model.py` — archive downloads, chunk scan, provenance, sample, duplicate checks, model training/evaluation
- `tests/test_cfpb_narrative_model.py` — split, taxonomy, deterministic sampling, exact and near-duplicate behavior
- `src/streamlit_app.py` — preserved structured trend dashboard plus archived-text tab; input is local, form-cleared, and not written to project data/model files
- `src/generate_report.py` — generates case study with current metrics and coverage caveats
- `model_card.md`, `CFPB_SOURCE_ASSESSMENT.md`, `CFPB_TASK_DEFINITION.md`, `technical_report.md`, `policy_memo.md`, `README.md`, and this handoff — updated to distinguish current structured trends from the archive model
- `CFPB_NARRATIVE_MODEL_MANIFEST.json` — archive provenance, coverage, missingness, taxonomy changes, duplicate checks
- `output/cfpb_narrative_model_metrics.json` — validation/test metrics, per-class results, and confusion matrices
- `output/cfpb_narrative_sample.parquet` and `complaint_narrative_tfidf_logreg.joblib` — local, ignored text sample/model artifacts

## Validation

- `python3 -m compileall -q src tests`: passed.
- `python3 -m unittest discover -s tests -v`: **15 tests passed**, including the new near-duplicate test.
- `python3 src/cfpb_narrative_model.py`: completed successfully; rebuilt local sample, model, manifest, and metrics.
- Saved-model smoke test: loaded the local artifact and produced a valid 11-class prediction with normalized, uncalibrated scores.
- Streamlit AppTest: passed with both dashboard tabs rendered, seven metrics displayed, and no app exceptions.
- Loopback browser check: submitted synthetic text, confirmed a local prediction rendered and the text field cleared after submission; the test server was stopped afterward.
- `python3 src/generate_report.py`: passed and regenerated `CASE_STUDY.md` with the current evaluation and coverage limits.

## Reproduction

From the standalone project folder:

```bash
make narrative-model
make test
make run
make report
make app
```

`make app` binds to `127.0.0.1`. Do not push, publish, upload, or deploy these artifacts. Keep the local raw archives, sample, and model out of version control.

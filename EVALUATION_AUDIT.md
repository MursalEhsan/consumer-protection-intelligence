# Archived Narrative Classifier: Evaluation Audit

## Scope and conclusion

This audit examines the saved sample, model, and metrics without changing or retraining the classifier. The primary final-test result remains the existing result: **0.6294 accuracy, 0.3939 macro-F1, and 0.6236 weighted-F1 on 18,215 rows**. Do not treat this as a pristine, population-representative estimate: duplicate filtering materially changed the sample, test label distribution differs sharply from training, and an earlier exact-dedup-only test result had already been inspected before the near-duplicate filter was added.

The source is the separate official [CFPB Consumer Complaint Database Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/). These results do not describe the current structured-data trend source, and they make no claim about narratives received after 2026-08-14.

## Split dates, sizes, and sampling

The configured periods in [`src/cfpb_narrative_model.py`](./src/cfpb_narrative_model.py) are disjoint and chronological. “Observed sample dates” are the min/max dates actually present after filtering; the August archive's last selected eligible narrative was received August 11, not August 14.

| Split | Configured received-date window | Observed sample dates | Final rows |
|---|---|---|---:|
| Train | 2024-11-01–2025-10-31 | 2024-11-01–2025-10-31 | 39,760 |
| Validation | 2025-11-01–2025-12-31 | 2025-11-01–2025-12-31 | 12,552 |
| Final test | 2026-01-01–2026-08-14 | 2026-01-01–2026-08-11 | 18,215 |

Eligibility requires nonblank narrative, nonblank `Issue`, valid `Date received`, and nonblank `Complaint ID`. The archive scan covered 11,917,416 source rows and found 1,789,934 eligible records across the selected exports. The oldest selected export contributed 291,574 eligible narratives received 2015–2018, outside all model windows. There were 1,498,360 eligible records inside the three model windows.

The 100,000 pre-dedup sample was selected separately within each window by deterministic bottom-hash ranking on Complaint ID: BLAKE2b of `427:<Complaint ID>`, with seed 427 and fixed quotas of 60,000 train / 20,000 validation / 20,000 test. This is not issue-stratified sampling. The respective in-window eligible pools were 1,242,325 / 134,641 / 121,394, so the pre-dedup sampling fractions differed: 4.83% / 14.85% / 16.48%.

### Eligible-record exclusions

| Step | Rows excluded at step | Rows remaining |
|---|---:|---:|
| Eligible records in all selected exports | — | 1,789,934 |
| Outside train/validation/test date windows | 291,574 | 1,498,360 |
| Not selected by the 100,000-row per-split quotas | 1,398,360 | 100,000 |
| Duplicate Complaint IDs | 0 | 100,000 |
| Exact normalized duplicate narratives | 28,813 | 71,187 |
| Approximate cross-split near duplicates removed | 660 | 70,527 |

Thus 1,719,407 eligible source rows are outside the final model sample for those stated reasons. Duplicate filtering removed 29.47% of the pre-dedup sample. Combined exact-plus-near removal by split was 20,240/60,000 train rows (33.73%), 7,448/20,000 validation rows (37.24%), and 1,785/20,000 test rows (8.93%). The filter manifest does not break those per-split counts down separately into exact versus near-duplicate removals.

## Class counts after train-only taxonomy mapping

The counts below refer to the final, post-dedup modeling sample. The ten named classes were selected from train; every other source `Issue` maps to the pooled Other target.

| Target class | Train | Validation | Final test |
|---|---:|---:|---:|
| Attempts to collect debt not owed | 1,766 | 707 | 2,432 |
| False statements or representation | 638 | 290 | 845 |
| Improper use of your report | 7,118 | 1,355 | 136 |
| Incorrect information on your report | 14,728 | 4,769 | 619 |
| Managing an account | 1,248 | 568 | 2,016 |
| Other / outside selected training taxonomy | 6,272 | 2,872 | 9,162 |
| Other transaction problem | 1,162 | 65 | 234 |
| Problem with a company's investigation into an existing problem | 5,280 | 1,221 | 277 |
| Problem with a purchase shown on your statement | 497 | 280 | 1,180 |
| Took or threatened to take negative or legal action | 389 | 134 | 470 |
| Written notification about debt | 662 | 291 | 844 |
| **Total** | **39,760** | **12,552** | **18,215** |

## Baseline and full held-out metrics

The dashboard's “+0.595 vs baseline” is the absolute accuracy difference between the TF-IDF/logistic-regression model and a **training-majority `DummyClassifier`**. The baseline was fit on the same mapped training labels and predicted the same 18,215 final-test rows as the model. Its training-majority class was `Incorrect information on your report` (14,728/39,760 training rows, 37.04%); that label accounts for only 619/18,215 test rows (3.40%), explaining the unusually weak test baseline.

| Model, same final-test rows | Accuracy | Macro-F1 | Weighted-F1 | Rows |
|---|---:|---:|---:|---:|
| Training-majority `DummyClassifier` | 0.0340 | 0.0060 | 0.0022 | 18,215 |
| TF-IDF + logistic regression | 0.6294 | 0.3939 | 0.6236 | 18,215 |

The dashboard's `+0.595` is **+59.54 percentage points**, not a 59.5% relative improvement. The baseline predicts one label for every test row; its metrics are poor under the observed temporal shift. The size of this delta should not be read as evidence of broad real-world quality.

## Full-test per-class metrics

These are the saved model's test-set metrics for the full operational test population after mapping to the 11-class target. Precision, recall, and F1 are zero-division-safe.

| Actual mapped class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Attempts to collect debt not owed | 0.579 | 0.535 | 0.556 | 2,432 |
| False statements or representation | 0.459 | 0.236 | 0.311 | 845 |
| Improper use of your report | 0.227 | 0.471 | 0.306 | 136 |
| Incorrect information on your report | 0.272 | 0.533 | 0.360 | 619 |
| Managing an account | 0.570 | 0.542 | 0.555 | 2,016 |
| Other / outside selected training taxonomy | 0.768 | 0.799 | 0.784 | 9,162 |
| Other transaction problem | 0.500 | 0.038 | 0.071 | 234 |
| Problem with a company's investigation into an existing problem | 0.177 | 0.357 | 0.237 | 277 |
| Problem with a purchase shown on your statement | 0.615 | 0.649 | 0.631 | 1,180 |
| Took or threatened to take negative or legal action | 0.358 | 0.166 | 0.227 | 470 |
| Written notification about debt | 0.373 | 0.243 | 0.294 | 844 |

## Full-test confusion matrix

Rows are actual classes; columns are predicted classes. Indices correspond to the numbered class order below. Matrix values are counts from the unchanged saved model on the 18,215 final-test rows.

| Index | Class |
|---:|---|
| 0 | Attempts to collect debt not owed |
| 1 | False statements or representation |
| 2 | Improper use of your report |
| 3 | Incorrect information on your report |
| 4 | Managing an account |
| 5 | Other / outside selected training taxonomy |
| 6 | Other transaction problem |
| 7 | Problem with a company's investigation into an existing problem |
| 8 | Problem with a purchase shown on your statement |
| 9 | Took or threatened to take negative or legal action |
| 10 | Written notification about debt |

| Actual \ Predicted | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **0** | 1,300 | 120 | 61 | 285 | 4 | 279 | 0 | 131 | 23 | 25 | 204 |
| **1** | 278 | 199 | 11 | 77 | 1 | 141 | 0 | 66 | 1 | 20 | 51 |
| **2** | 3 | 1 | 64 | 39 | 0 | 17 | 0 | 11 | 0 | 1 | 0 |
| **3** | 25 | 2 | 44 | 330 | 1 | 123 | 0 | 86 | 2 | 0 | 6 |
| **4** | 1 | 0 | 1 | 1 | 1,092 | 806 | 2 | 1 | 112 | 0 | 0 |
| **5** | 219 | 20 | 75 | 280 | 738 | 7,323 | 7 | 97 | 327 | 32 | 44 |
| **6** | 1 | 0 | 0 | 0 | 43 | 174 | 9 | 0 | 7 | 0 | 0 |
| **7** | 7 | 1 | 6 | 71 | 1 | 84 | 0 | 99 | 6 | 0 | 2 |
| **8** | 7 | 1 | 0 | 11 | 35 | 348 | 0 | 12 | 766 | 0 | 0 |
| **9** | 131 | 16 | 14 | 59 | 2 | 113 | 0 | 18 | 2 | 78 | 37 |
| **10** | 275 | 74 | 6 | 62 | 0 | 122 | 0 | 38 | 0 | 62 | 205 |

## Other is a pooled target, not unknown-category detection

The code chooses the ten most frequent training `Issue` labels with at least 100 training examples, then maps every other source label to `Other / outside selected training taxonomy`. In train, 72 distinct source labels were pooled into Other; these were all labels present in train but excluded from the selected top ten. The resulting target is a heterogeneous mixture, not a single CFPB issue and not a novelty-detection mechanism.

| Split | Pooled Other rows | Share of split | Distinct pooled source labels | Rows with source label never seen in any train label |
|---|---:|---:|---:|---:|
| Train | 6,272 | 15.8% | 72 | 0 |
| Validation | 2,872 | 22.9% | 72 | 5 |
| Final test | 9,162 | 50.3% | 72 | 8 |

The five validation rows belong to four labels never seen in train; the eight test rows belong to three such labels. The remaining 2,867 validation and 9,154 test Other rows had source labels that appeared somewhere in training but fell outside the top-ten target taxonomy. A prediction of Other therefore means “the model's pooled Other class won,” not “the system detected a previously unknown CFPB category.”

## Established-category diagnostic (secondary, conditional result)

To separate the selected training taxonomy from the pooled Other population, the same fixed test predictions were additionally scored only on rows whose actual source `Issue` is one of the ten train-selected labels. This is a **post hoc, label-conditioned subset** of the existing test, not the full operational test population and not a replacement for the headline result. It contains 9,053 rows (49.7%); the other 9,162 rows are omitted from this diagnostic.

| Model on test rows whose actual label is in the train-selected top ten | Accuracy | Macro-F1 | Weighted-F1 | Rows |
|---|---:|---:|---:|---:|
| Training-majority `DummyClassifier` | 0.0684 | 0.0128 | 0.0088 | 9,053 |
| Same TF-IDF + logistic-regression predictions | 0.4575 | 0.3994 | 0.5189 | 9,053 |

This conditional result is lower in accuracy than the full-population result because the full test has a large, comparatively well-predicted Other class. It should not be generalized to the excluded categories or used to select a new model.

## Taxonomy and temporal shift

The archive manifest counts distinct `Issue` strings observed among eligible narratives by year. The “new” and “no longer observed” counts compare each observed year with the preceding **observed** year; they are not proof of official taxonomy revisions. The selected exports omit 2019–2023, 2018 is only through April, 2024 starts in November, and observed category absence may simply mean no eligible record was present.

| Received year | Distinct eligible Issue strings observed | Newly observed vs prior observed year | No longer observed vs prior observed year |
|---:|---:|---:|---:|
| 2015 | 90 | 90 (initial observed year) | 0 |
| 2016 | 89 | 0 | 1 |
| 2017 | 158 | 71 | 2 |
| 2018 (partial through April) | 78 | 0 | 80 |
| 2024 (November onward) | 86 | 13 | 5 |
| 2025 | 89 | 3 | 0 |
| 2026 (through August) | 88 | 0 | 1 |

There are concrete signs of naming/category instability: for example, training includes both “Problem with a company's investigation into an existing problem” (5,280 rows, selected) and “Problem with a company's investigation into an existing issue” (50 rows, pooled into Other). The current pipeline treats these as different strings.

The mapped class distribution shift is large. Total variation distance from train was 0.1306 for validation and **0.6420 for test**; Jensen–Shannon distance (base 2) was 0.1522 and **0.5994**, respectively. In particular:

- `Incorrect information on your report`: 37.04% train / 37.99% validation / **3.40% test**.
- `Improper use of your report`: 17.90% / 10.80% / **0.75%**.
- `Other / outside selected training taxonomy`: 15.77% / 22.88% / **50.30%**.
- `Attempts to collect debt not owed`: 4.44% / 5.63% / **13.35%**.
- `Managing an account`: 3.14% / 4.53% / **11.07%**.

The macro-F1 and per-class table should therefore accompany accuracy; even this chronological test is a sample from the selected archive, not evidence for current or post-archive narrative performance.

## Leakage, fitting, and test-set integrity

### What the implementation does

- **Vocabulary:** `TfidfVectorizer` is inside the pipeline and fitted only by `model.fit(X_train, y_train)`. IDF and vocabulary therefore use train text only.
- **Vocabulary/preprocessing settings:** lowercase, Unicode accent stripping, word unigrams and bigrams, `min_df=2`, maximum 100,000 features, sublinear term frequency, `float32`. The vectorizer learns the actual vocabulary only from the training split.
- **Label selection:** the top-ten taxonomy and Other mapping are derived from training labels only.
- **Preprocessing:** eligibility filtering uses required fields before sampling. The model's vectorizer lowercases, strips accents, and constructs word 1–2 grams; it learns its vocabulary on train only. Case/whitespace normalization is used for exact deduplication, not to fit the model.
- **Estimator:** the current code fixes `C=2`, `class_weight="balanced"`, `liblinear`, `max_iter=400`, `tol=1e-3`, and seed 427. The code has no grid search or test-driven parameter selection; validation and test are evaluated after fitting.
- **Selection/thresholds:** only this single model configuration is implemented; there is no grid search, validation-based model-selection loop, or manually selected classification threshold. `predict` uses the estimator's default multiclass decision rule. `predict_proba` scores are uncalibrated. The near-duplicate filter's Hamming threshold (3), bucket cap (150), and minimum four-word rule are fixed implementation constants, not learned from labels; the code has no metric-search path for them. Given the earlier test exposure described below, historical selection of any manual constants cannot be certified as test-blind.
- **Baseline:** the DummyClassifier is fit on mapped train labels only.

### What cannot be certified

The source code shows train-only fitting and no parameter-search path, but it cannot establish the historical intent behind manually chosen constants. More importantly, the exact-dedup-only test metrics had already been generated and inspected before the approximate near-duplicate filter was added. That filter was introduced as leakage control, not as a documented hyperparameter adjustment, but it removed test rows and changed the final test sample after a prior test result was visible. Therefore, the current test is **not a pristine blind holdout**. No further tuning should use it; preserve the current artifact and obtain a newly locked chronological holdout before future model selection or claims.

## Duplicate filtering and representativeness

1. **Complaint IDs:** the selected sample had zero duplicate-ID rows and zero IDs crossing splits. IDs were used for hash sampling/checks and then removed from persisted sample text.
2. **Exact narrative duplicates:** text is case-folded and whitespace-normalized, SHA-256 hashed, sorted by received date/ID/hash, and deduplicated across the entire sample (including duplicates within the same split). The earliest record is retained. There were 28,813 duplicate rows; 574 exact-text groups crossed temporal splits before removal and zero afterward. `Issue` labels are not consulted.
3. **Approximate cross-split duplicates:** 64-bit SimHash signatures are built over unique word trigrams. Four 16-bit locality-sensitive bands propose pairs; candidates from different splits are verified at Hamming distance ≤3. For matches, the later record is removed. The filter removed 660 rows from 2,557 qualifying pairs. It skips narratives shorter than four tokens and buckets larger than 150; three oversized buckets were skipped. The count of short-text skips is not recorded. No qualifying pair remained in the checked buckets, which does not prove the unexamined/skipped cases are duplicate-free.

Neither filter uses labels, but both condition inclusion on text similarity and/or date. Exact duplicates are also removed within partitions, and later cross-partition copies are preferentially removed. This yields a unique/near-unique-text evaluation set rather than a random sample of all eligible operational complaints. Unequal split attrition (33.7% train, 37.2% validation, 8.9% test) can alter label frequencies and makes the test's representativeness a material limitation. The code should preserve and report an unfiltered population-style test alongside a cluster-aware leakage-safe diagnostic in future runs, rather than silently treating deduplicated test metrics as the only population estimate.

## Vocabulary/model-selection audit

No evidence in the implementation indicates test outcomes were used in fitting: fitting and label selection are train-only, and test scoring occurs after fitting. However, the prior exact-only test result was seen before final duplicate policy was completed, so full historical test-blindness cannot be verified. The current model parameters, taxonomy rule, filtering thresholds, and test results must be frozen from this point forward. Future selection should use training plus validation only and report once on a new locked holdout.

## Dashboard CONNECTING status

The previous local smoke-test server on port 8502 was stopped after its check. A browser tab left open at `127.0.0.1:8502` consequently showed a Streamlit connecting/loading state; this was a stopped local server, not a model or data failure. I restarted Streamlit bound to `127.0.0.1:8502`, verified `/_stcore/health` returned `ok`, loaded both dashboard tabs in the browser, and submitted synthetic text. A prediction rendered, the input field cleared, and no Streamlit app exception occurred. The temporary server is stopped after verification; run `make app` locally to reopen the dashboard.

## Findings and prioritized fixes (no model changes made)

1. **High — test is exposed.** An earlier exact-only test result was inspected before near-duplicate filtering changed the test sample. Keep the current model/result intact but label this set retrospective; lock a new future chronological holdout before tuning or making confirmatory claims.
2. **High — severe temporal/taxonomy shift.** Test total-variation distance is 0.6420 and 50.3% maps to pooled Other. Full accuracy (0.6294) is partly driven by this large Other class; on selected-taxonomy test rows alone accuracy is 0.4575. Report both populations and per-class results, as above.
3. **High — Other is not novelty detection.** Most test Other rows (9,154/9,162) have source labels seen during training but omitted from top ten. Replace the single pooled category with an explicitly versioned taxonomy/mapping or an independently justified open-set design in future work; do not relabel existing results.
4. **Medium — dedup changes the evaluation population.** Record per-split counts at every filter stage, skipped short-text counts, cluster membership, and reasons. In future, keep duplicate clusters together when splitting and report both natural-population and duplicate-controlled views; do not retrospectively tune this test.
5. **Medium — observed-year taxonomy is not a version history.** Archive coverage gaps and partial years make “new/disappeared” string counts ambiguous. Add official dated taxonomy/version evidence and distinguish taxonomy edits from labels not observed in a batch.
6. **Medium — sampling provenance fields can mislead.** `train_and_evaluate` receives an already deduplicated sample, so its `sampled_rows_by_split` and `deduplicated_rows_by_split` fields are currently identical final counts. Use provenance's `sample_selected_before_duplicate_removal` for the true 60k/20k/20k selected counts; rename or correct the redundant metric fields in a future code change.
7. **Resolved presentation issue — dashboard delta labeling.** The previous “+0.595 vs baseline” is +59.54 percentage points, not a relative percent lift. The local UI now states percentage-point units and names the training-majority class; its validation/test details include baseline and model metrics. This changes presentation only, not saved model results.
8. **Resolved operational issue — local CONNECTING state.** The app was stopped, then restarted and browser-verified on loopback. No application exception was found; the dashboard is not left running.

## Evidence files

- [`src/cfpb_narrative_model.py`](./src/cfpb_narrative_model.py): split, sample, label mapping, duplicate filtering, fit, and evaluation logic.
- `CFPB_NARRATIVE_MODEL_MANIFEST.json` and `output/cfpb_narrative_model_metrics.json`: generated local-only provenance and metrics artifacts; not included in this repository.
- `output/cfpb_narrative_sample.parquet`: local-only sample containing complaint narratives; intentionally not included in this repository.
- [`src/streamlit_app.py`](./src/streamlit_app.py): separate current structured-trend and archived-text dashboard surfaces.

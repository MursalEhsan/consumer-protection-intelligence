# Development handoff

## Current review state

This is a local review diff only. The project began this review on branch `main` at commit `02de6a7`; the work here has not been committed, pushed, or deployed. The GitHub repository is public per the owner's request, but this review did not publish the working changes.

The prior handoff also recorded 15 passing tests. This review independently ran the current suite: 15 tests passed.

## Structured-data evidence reproduced locally

- `make run` completed against the official structured CFPB bulk archive. It scanned 19,028,339 source rows, used a deterministic 100,000-row sample for the local warehouse, detected no narrative field, and recorded coverage from 2011-12-01 through 2026-11-09.
- Retrieval time in the generated local manifest: 2026-11-10 UTC. The maturity rule marks 2026-09 as the latest complete month (cutoff 2026-10-26).
- Full-source SQL view results for 2026-09: `Incorrect information on your report` had 371,428 / 660,839 valid-date complaints = 56.2055%. The numerator and denominator come from full-source aggregate tables, not the sample.
- No issue met the existing screen in 2026-09. The most recent prior flag was June 2026: `Problem with a company's investigation into an existing issue`, 922 / 620,905 = 0.1485%, against 0.0621% mean for observed June 2021-2025 rows. The exact label occurs in all five observed baseline months. A closely named investigation category is counted separately; labels are not harmonized.
- The candidate rule omits absent issue-month rows rather than filling zeroes; its last-five comparison is the last five observed same-month rows. This and possible label changes are interpretation risks, not resolved taxonomy findings.
- `make report` completed via the Makefile entry point and generated `reports/structured_trends.md` and `reports/issue_trends.png` with aggregate data only. Raw archive, SQLite warehouse, manifest, CSVs, and sample are ignored local artifacts.

## Archived classifier

The classifier remains frozen; it was not retrained in this review. The local narrative manifest, sample, and metrics JSON were absent before the structured workflow and remain unavailable. The tracked `EVALUATION_AUDIT.md` was used as the durable evidence:

- The confusion matrix sums to 18,215 final-test rows and 11,465 correct predictions (62.9426% accuracy).
- The ten named classes contain 9,053 rows, with 4,142 correct (45.7528%); 9,162/18,215 (50.2992%) are mapped to pooled Other.
- The reported training-majority baseline predicts `Incorrect information on your report`; the recorded accuracy gap is 59.54 percentage points. The baseline degrades under temporal label shift.
- An earlier exact-dedup-only test result had been inspected before the final duplicate filter was settled. Preserve the audit's warning that this is not a pristine blind holdout. No post-2026-08-14 narrative performance is claimed.

The structured snapshot and archived-text test have different coverage and must remain separate.

## Portfolio administration suggestions

Suggested GitHub About text: `Local-first analysis of CFPB complaint trends and historical archived-narrative classification, with reproducible SQL, evaluation audits, and explicit data limitations.`

Suggested topics: `consumer-protection`, `cfpb`, `data-analysis`, `data-visualization`, `sqlite`, `natural-language-processing`, `scikit-learn`, `streamlit`.

No application narrative or portfolio conclusion is supplied here; the owner will write and approve those.

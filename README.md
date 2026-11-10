# Consumer Protection Intelligence

An evidence-led exploration of published CFPB consumer complaints, with separate structured-trend and historical narrative-classification workflows.

## Structured-data case study

**Question:** How does the mix of published complaint issue labels change over time?

The latest reproducible local snapshot was retrieved on 2026-11-10 UTC, covers complaints received through 2026-11-09, and includes complete months through 2026-09 under the project's 15-day maturity rule. In September 2026, `Incorrect information on your report` accounted for **371,428 of 660,839 complaints (56.21%)**. The numerator and denominator are full-source monthly aggregates, not counts from the capped 100,000-row sample. See the [dated aggregate report](reports/structured_trends.md) and [monthly-share chart](reports/issue_trends.png).

No issue met the existing exploratory screening rule in September 2026. Its most recent earlier flag was in June 2026: `Problem with a company's investigation into an existing issue` had 922 of 620,905 complaints (0.1485%), compared with a 0.0621% mean for the same label in June 2021-2025. The label was observed in each of those five comparison months, but similar investigation issue labels are counted separately and are not harmonized. The flag is a review prompt, not evidence of a verified incident or harm.

The exact SQLite view query is in [`sql/monthly_issue_trends.sql`](sql/monthly_issue_trends.sql) and is executed by [`src/cfpb_pipeline.py`](src/cfpb_pipeline.py). It divides full-source issue counts by full-source valid-date monthly totals. The trend method and limits are summarized in the [technical report](docs/technical_report.md); the [source assessment](docs/CFPB_SOURCE_ASSESSMENT.md) explains CFPB publication and representation caveats.

## Archived narrative classifier case study

The separate historical model's committed [evaluation audit](EVALUATION_AUDIT.md) reports 62.94% accuracy on 18,215 held-out archived narratives, versus 3.40% for a training-majority baseline that always predicted `Incorrect information on your report`: a 59.54 percentage-point accuracy difference. The audit confusion matrix arithmetically reconciles to 45.75% accuracy on the 9,053 test rows in the ten named categories, while 50.3% of all test rows map to a heterogeneous `Other` class. These are historical archive results, not current-text performance. A prior exact-dedup-only test result had been inspected before the final duplicate filter was settled, so the holdout is not pristine or confirmatory. See the [model card](docs/model_card.md) and [full audit](EVALUATION_AUDIT.md) for the limitations.

Structured trend coverage is through 2026-09; the narrative model's selected archive test ends 2026-08-14. The structured source has no narrative text and does not extend the text model's evaluation coverage. The historical metrics above were checked against the committed audit table in this review; generated narrative manifests, samples, and model binaries are local-only and are not included.

## Local reproduction

Requires Python 3.10+ and internet access to retrieve CFPB's public structured archive (about 365 MB compressed at the reviewed URL).

```bash
python3 -m venv .venv
source .venv/bin/activate
make setup
make run
make report
make test
make app
```

`make run` scans the public structured archive and produces ignored local aggregates and manifests. `make report` reruns that pipeline and regenerates the aggregate-only report and chart under `reports/`. `make narrative-model` downloads selected official archive exports and rebuilds the historical model; it is not needed to reproduce the structured report and was not run for this review. `make app` binds Streamlit to `127.0.0.1:8501`. No dashboard deployment is configured.

## Repository map

- [`reports/`](reports/) - dated aggregate-only structured result and chart; no narrative text or complaint IDs
- [`sql/monthly_issue_trends.sql`](sql/monthly_issue_trends.sql) - SQL view for full-source counts and shares
- [`EVALUATION_AUDIT.md`](EVALUATION_AUDIT.md) - archived classifier evaluation, baselines, taxonomy shift, and caveats
- [`docs/`](docs/) - source, data, modeling, and interpretation methods
- [`docs/development/`](docs/development/) - handoff and interview preparation notes
- [`src/`](src/) and [`tests/`](tests/) - implementation and regression/unit tests

Raw exports, local samples, complaint text, generated manifests, databases, and trained model files are excluded from Git.

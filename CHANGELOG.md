# v0.2.0

- Reconciled the [historical matrix](reports/historical_matrix_audit.json) and published a [separate, frozen evaluation](reports/classifier_eval.md).
- Added [product-level replay and event comparisons](reports/backtest.md), [spike injection](reports/spike_power.csv), and [narrative timing against the retained rule](reports/lead_vs_retained.json).
- Published the [checksum and URL for the numeric model](config/model_asset.json); the viewer supports calibrated abstention.
- Added a [fixture smoke run](Makefile), [verification workflow](.github/workflows/verify.yml), [client brief](docs/client_brief.md), and [deployment instructions](docs/deployment.md).

Frozen model: tfidf_svc. Accuracy difference from retrospective test-majority oracle: 21.49 percentage points.

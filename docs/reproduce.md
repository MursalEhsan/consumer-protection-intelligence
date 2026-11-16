# Reproduce and inspect the release

For the small fixture use make demo and make test. For the historical experiments install the Python 3.12 requirements-model.lock in a virtual environment, export PYTHONPATH=src:scripts, and work in a separate clone. The public source files may be revised. Hash mismatches stop archive downloads.

    python scripts/archive_inputs.py output/archives
    python scripts/fresh_eval.py fit output/archives

Inspect the validation freeze. Commit config/, the scoring code and reports/frozen_choices.json before scoring. Then run the following once in the experiment checkout.

    python scripts/fresh_eval.py evaluate output/archives
    python scripts/export_model.py
    python scripts/shortcut_check.py output/archives
    python scripts/cluster_sample.py output/archives
    python scripts/clusters.py

Fetch the structured source with make run. To reproduce archived values, verify the snapshot SHA against reports/product_monthly.json before comparing; make run on the current CFPB bulk file may produce a new vintage. The checked-in aggregates reproduce downstream results independently of a future bulk revision.

    python scripts/detector.py
    python scripts/backtest.py
    python scripts/injection.py
    python scripts/lead_time.py
    python scripts/retained_lead.py
    python scripts/readme_report.py

A local frozen.joblib includes the duplicate filter and is private training material. Never upload it. Only export and publish the numeric-only complaint-svc.npz. The app downloads that file from the release, checks its SHA and loads it without pickle. The archived evaluation is fixed even if a future environment yields slightly different model coefficients.

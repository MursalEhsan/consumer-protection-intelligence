# Consumer Protection Intelligence

A reproducible, local-only source assessment and aggregate-trend exploration project for the official CFPB Consumer Complaint Database.

## Status and scope

The project has two separate CFPB data workflows:

- The **current structured-data pipeline** measures full-archive coverage and descriptive issue trends. Its source snapshot contains no narrative field.
- The **historical narrative classifier** uses a separate, discontinuous set of official CFPB Narratives Archive exports. It trains a TF-IDF/logistic-regression baseline, uses chronological validation and test periods, and checks exact and approximate cross-split duplicates.

The narrative model is trained through 2025-10, validated on 2025-11–2025-12, and held out on 2026-01–2026-08-14. It is not evaluated on post-archive narratives or the current structured-data snapshot. See [model_card.md](model_card.md) and the generated `output/cfpb_narrative_model_metrics.json` for measured results. Neither workflow provides market-wide prevalence estimates or verified harm findings.

## What the project does

1. Downloads and hashes the public CFPB bulk archive when a matching local snapshot is not already available.
2. Streams the full archive in chunks to calculate exact row counts, date coverage, checked-field missingness, monthly issue counts, and yearly issue taxonomies.
3. Creates a deterministic sample capped at 100,000 rows, removes complaint IDs before persistence, and stores the reduced sample and full-source aggregates in a local SQLite warehouse.
4. Excludes complaint months until a conservative 15-day publication-maturity cutoff is met.
5. Produces a monthly trend table, exploratory same-calendar-month issue-share candidates, a source manifest, and a local dashboard.
6. Separately samples verified archived narratives, records archive coverage and label changes, removes exact and high-similarity cross-period duplicates, and evaluates a TF-IDF/logistic-regression model against a majority baseline.

The anomaly candidates are analyst prompts, not confirmed incidents, causal findings, or evidence of harm. The source labels are operational categories, not adjudicated ground truth. CFPB also cautions that complaint data are not representative of all consumer marketplace experiences.

## Run locally

Requirements: Python 3.10+ and a local Python environment. The dashboard binds only to `127.0.0.1:8501`.

```bash
cd consumer-protection-intelligence
python3 -m venv .venv
source .venv/bin/activate
make setup
make run
make narrative-model
make test
make report
make app
```

`make run` retrieves the official CFPB structured-data archive when needed and builds local trend outputs. `make narrative-model` retrieves the selected official Narratives Archive ZIP exports when needed, scans them in chunks, and rebuilds the local narrative sample, model, provenance manifest, and evaluation metrics. Both commands use public CFPB sources; they may download large archives and require internet access. Generated datasets, manifests, models, and reports are ignored by Git and are not included in this repository. `make report` regenerates the local `CASE_STUDY.md` after `make run`.

The selected narrative exports do not provide continuous coverage; consult the generated provenance and evaluation outputs before interpreting results. The maximum persisted modeling sample is 100,000 rows before duplicate filtering.

All analysis and dashboard use are local. No data are uploaded by the project, no external LLM calls are made, and this repository does not publish or deploy results. Dashboard text input is processed by the local model and is not written to the project dataset or model artifacts.

## Outputs

- `CFPB_DATA_MANIFEST.json` and `output/cfpb_data_quality.json` — generated structured-source provenance and quality details
- `output/issue_trends_monthly.csv` and `output/emerging_issue_candidates.csv` — generated full-source trends and review prompts
- `CFPB_NARRATIVE_MODEL_MANIFEST.json` and `output/cfpb_narrative_model_metrics.json` — generated archive provenance and chronological evaluation
- `complaint_narrative_tfidf_logreg.joblib` — generated local narrative classifier
- `complaints_warehouse.db` — generated local sample and full-source monthly aggregates in SQLite
- `CASE_STUDY.md` and `output/issue_trends.png` — generated report and descriptive chart

These are local generated outputs, ignored by Git; regenerate them with the commands above.

The database retains only the sampled `Date received`, `Product`, `Sub-product`, `Issue`, and `Submitted via` fields plus aggregate issue counts and totals. Complaint IDs are used only for deterministic sampling and duplicate checks; they are removed before persistence.

## Key documentation and code

- [CFPB_SOURCE_ASSESSMENT.md](CFPB_SOURCE_ASSESSMENT.md) — source feasibility and CFPB publication constraints
- [CFPB_TASK_DEFINITION.md](CFPB_TASK_DEFINITION.md) — current task scope and stop condition
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md) — source and derived fields
- [technical_report.md](technical_report.md) — methods and limitations
- [model_card.md](model_card.md) — archived narrative classifier evaluation and intended-use boundaries
- [monitoring_plan.md](monitoring_plan.md) — source and trend monitoring
- [policy_memo.md](policy_memo.md) — interpretation guardrails
- [demo_walkthrough.md](demo_walkthrough.md) — truthful dashboard demonstration
- [technical_interview_walkthrough.md](technical_interview_walkthrough.md) — engineering and evidence framing
- [OVERNIGHT_HANDOFF.md](OVERNIGHT_HANDOFF.md) — execution status, validation, and handoff
- `src/cfpb_pipeline.py` — full-source chunk scan, sample creation, SQLite, trends, and candidate screening
- `src/cfpb_source_assessment.py` — reproducible source manifest
- `src/streamlit_app.py` — loopback-only dashboard with distinct current-trends and archived-text tabs
- `src/cfpb_narrative_model.py` — official archive ingestion, provenance, leakage checks, training, and evaluation

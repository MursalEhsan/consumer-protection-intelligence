# Five-Minute Demonstration Walkthrough

## 0:00-0:45 — State the two data scopes

The current structured CFPB database contains no narrative field. Separately, the official historical Narratives Archive contains usable text and supports a bounded baseline. The archived model's held-out cutoff is 2026-08-14; it has not been evaluated on post-archive text or the current structured snapshot.

## 0:45-1:30 — Source and limitations

Start with [`reports/structured_trends.md`](../reports/structured_trends.md) and its chart. The generated full-source manifests are local-only (`CFPB_DATA_MANIFEST.json` and `CFPB_NARRATIVE_MODEL_MANIFEST.json`); do not imply that these are checked into Git. Distinguish the current structured archive from the separate discontinuous narrative exports. Mention that CFPB complaint data are not representative of all marketplace experiences.

## 1:30-2:20 — Reproducible, local pipelines

Run `make run` for the current structured trends. `make narrative-model` independently rebuilds the historical narrative sample, model, and metrics; it was not needed to reproduce the public report. Explain the 100,000-row structured sample cap, chronological classifier splits, duplicate checks, and majority baseline.

## 2:20-3:20 — Trend dashboard

Run `make app`, which binds to `127.0.0.1:8501`. In the current structured trends tab, select a complete-month range and a small set of issue categories. Explain that displayed shares use full-source monthly denominators.

## 3:20-4:20 — Archived classifier

Show the archive model evaluation and, if authorized, use a short non-sensitive text example in the local inference form. Explain that the target is an archive `Issue` category, the taxonomy is bounded and training-derived, and scores are uncalibrated. Do not retain or present user-entered personal complaint text.

## 4:20-5:00 — Close with evidence limits

Review trend candidates as analyst prompts, not verified incidents or evidence of harm. Close by stating the coverage gap, the August 14, 2026 text-model cutoff, absence of human label audit, and separation from later structured trends.

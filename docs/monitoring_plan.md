# Source and Trend Monitoring Plan

## Status

A baseline classifier is trained and evaluated for a fixed set of archived narratives, but it is not deployed or continuously updated. Model evaluation applies only through the 2026-08-14 held-out cutoff. Monitoring covers the current structured-data trend pipeline separately from archive/model provenance; it does not imply post-archive text validation.

## Each source refresh

- Record source URL, retrieval time, archive SHA-256, full row count, date coverage, and column names.
- Compare schema fields and narrative-field candidates with the previous snapshot.
- Recheck full-archive missingness for present source fields and invalid received dates.
- Confirm sample size does not exceed 100,000 and complaint IDs are removed before persistence.
- Verify monthly issue counts sum to monthly denominators (including `Unknown` issue labels).
- Confirm the latest month included in trends satisfies the documented 15-day maturity rule.
- Keep current structured-source coverage separate from the archived text model's coverage and evaluation window.

## Archived narrative model reproduction

- Preserve the official archive page, each selected ZIP name and checksum, retrieval time, coverage, missingness, and yearly Issue taxonomy changes.
- Confirm each run's deterministic sampling, split boundaries, exact duplicate checks, and approximate cross-split near-duplicate checks.
- Re-run the chronological validation and final test against the majority baseline. Do not compare runs with changed sample, taxonomy, or archive versions as if they were the same evaluation.
- Do not claim performance on complaints received after 2026-08-14 or on the current structured-data snapshot.
- The fixed baseline is not an operational service; any newly trained model requires a new review and held-out evaluation plan.

## Aggregate trends and candidate prompts

- Recompute full-source monthly counts and shares; never use the capped sample as the denominator.
- Track the number of comparable prior same-calendar-month observations for each issue.
- Record candidate threshold, minimum count, baseline, source snapshot, and excluded immature months.
- Require human review and independent corroboration before treating a candidate as a policy signal.
- Do not calculate alert precision/recall without verified incident outcomes.

The current candidate rule is exploratory: at least three prior same-month observations, current count of at least 50, and an increase of at least three baseline standard deviations. This is not a calibrated significance test.

## Interpretation guardrails

- CFPB complaint data are not representative of all marketplace experiences.
- Complaint counts/shares are not market prevalence, verified incidents, or evidence of causation.
- Source `Issue` labels are operational categories, not adjudicated ground truth.
- Publication timing can make recent complaint months incomplete.
- A distribution shift may reflect source coverage, taxonomy, intake, or reporting changes rather than changes in underlying harm.

## Model monitoring limits

There is no online monitoring or deployment. Any subsequent archive data or taxonomy change requires a separately versioned dataset and evaluation; current structured complaint counts cannot serve as text-model drift or performance measurements.

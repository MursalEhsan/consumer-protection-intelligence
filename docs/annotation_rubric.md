# Label Audit Rubric and Evaluation Boundary

## Current status

The historical classifier was trained and evaluated using the source `Issue` field as its target. No human label audit or narrative annotation was performed. The official archive provides usable text, but source Issue categories remain operational labels, not adjudicated ground truth.

Do not fabricate human-reviewed labels, inter-annotator agreement, or label-accuracy estimates. Report the model only as a baseline for reproducing archive Issue labels, with its temporal and taxonomy limitations.

## Proposed protocol for a future label audit

1. Reconfirm source authorization, privacy requirements, retention policy, and coverage.
2. Draw a stratified sample from a new, temporally held-out archive period, with rare categories represented.
3. Hide source `Issue`, model prediction, company, geography, response outcomes, and complaint identifiers from annotators.
4. Provide only the narrative and the versioned CFPB taxonomy applicable to the complaint date.
5. Allow one taxonomy issue, multiple plausible issues, insufficient information, and taxonomy mismatch.
6. Have two trained annotators label each case independently; send disagreements to a third adjudicator.
7. Report raw agreement, an appropriate chance-corrected statistic, per-class disagreement, and the share marked ambiguous or insufficient.
8. Keep source labels, adjudicated audit labels, and model predictions in separate columns.
9. Use the audit for label-quality characterization and error analysis; never tune the existing final holdout against it.

The archived model has not been validated on post-2026-08-14 narratives or human-reviewed labels.

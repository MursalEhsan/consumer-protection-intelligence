# Remediation log

## Cleanup
Current state and defects. Development handoffs are tracked. PR #1 adds full-source year-over-year comparisons with null handling and candidate counts. Review the head and run tests before integration. gh and Docker are absent locally.

Changes and evidence. Copied the two handoffs outside the checkout, removed the tracked copies, and ignored docs/development/. No tracked notebooks found. Reviewed PR #1 and ran the tests at its exact head (19 passed). Requested a history-preserving merge. Manual repository description: "CFPB complaint trends and historical narrative classification with reproducible audits." Topics: consumer-protection, data-science, nlp, cfpb, risk-analytics.

## Historical classifier audit
Current state and defects. Read the audit, model card and training code. The training-majority comparator measures a deployable constant policy; the retrospective test majority is an oracle diagnostic. The report does not trace both to executable confusion-matrix arithmetic. Prior inspection before filtering compromises the holdout. Bounded SimHash skips oversized buckets and short texts. Changing label frequencies and repeated templates can distort evaluation. Redaction tokens, boilerplate and length are potential shortcuts; their effect is unmeasured.

Changes and evidence. src/audit_matrix.py reads the committed matrix and ordered labels, checks dimensions and recomputes per-class precision/recall, aggregate F1, and conditional accuracies. See reports/historical_matrix_audit.json. No refitting or new test observations. Deduplication and shortcut risks remain. A retrospective majority is not available to an operator choosing a constant prediction in advance.

PR #1 merged at 2e6a458 after tests passed. The remediation branch incorporates that merge without rebasing.

## Fresh evaluation
Current state and defects. The official CFPB archive currently lists August 2026 as its last export. The historical workflow used November 2024 onward. For a genuinely separate retrospective experiment, reserve August to October 2024; train and validate only before it. Do not examine held-out outcomes before freezing. Archive availability, actual publication timestamps, and independence beyond repository records still require checks.

## Product series and detector
Current state and defects. The SQL view divides by all products. The earlier rule does compute sample variance but uses very few historical observations. Monthly absence can reflect a taxonomy change; automatic merging by text is unjustified. Build product-denominated aggregates from the full dated structured archive and verify categories against the publisher.

## Backtest and narrative clusters
Current state and defects. The existing screen has no event register, predeclared event window, spike-injection benchmark or longitudinal cluster alignment. Press releases date announcements; complaints may precede enforcement. Unmatched alerts are not necessarily false positives.

## Client brief, engineering, deployment and final verification
Current state and defects. Review of Makefile, Dockerfile, app and tests shows no offline demo, CI, deployed app, calibrated abstention artifact or decision watchlist. The app stops when the local manifest is missing. Do not tag a release or publish new performance claims before the checks pass.

Detector implementation. Model within-product counts with trend and calendar month, a trailing window, overdispersion and a moment-matched predictive tail. Require two consecutive BH-adjusted upper-tail exceedances. Historical aggregates are from one revised snapshot. Count models remain sensitive to changes in product volume; a within-product share is reported separately. Only two wording families have explicit analyst mappings. Other historical transitions remain unresolved. Perfect-fit warnings occurred for low-variation histories; tail probabilities require empirical validation.

Backtest decision rule, set before calculating the comparison table: retain the legacy rule unless GLM has higher event recall with no higher unmatched annual workload. Rolling z and EWMA are additional comparators. Match event month through the next two months. Count uncovered events as misses, preserve duplicate-series events in the register and report their dependence. Unmatched alerts are a workload proxy, not verified false alarms.

Fresh evaluation evidence. Retrieved official exports outside the original model windows, fitted train-only models, selected by validation macro-F1 and froze the policy in Git. The first evaluation command stopped before opening the test set because the code tree was dirty. After committing, the scoring command ran once. The test receipt-date archive is retrospective and independent of the earlier code's documented splits. Export publication time is not available per complaint. Five models have per-class and aggregate bootstrap intervals. The constant comparator is separately identified as retrospective. A fine-tuned transformer was not pursued: the validation MiniLM baseline underperformed the sparse SVC; no evidence supported the extra compute under this budget.

Backtest evidence. Fifteen sourced public actions were registered before scoring. See reports/event_results.csv, backtest_table.csv and spike_power.csv. Some announcements coincide in date and category. Exact product taxonomy shortens history. The stricter GLM lost to the old rule under the prespecified adoption criterion. EWMA and rolling z matched more events at substantially greater analyst workload. Null activity is not a verified false positive.

Engineering and deployment evidence. Added a numeric-only GitHub model prerelease, checksummed asset loader, aggregate viewer and deployment instructions. A filesystem backup of development notes is outside Git. Metadata and topics were applied with GitHub CLI. No hosted app credentials available. No local Docker binary; remote CI must verify the image. The dashboard uses precomputed Parquet while keeping original SQLite SQL for legacy report compatibility.

Remaining taxonomy risk. Coverage inventory regression detects added, missing or changed spans and internal gaps. The two analyst mappings do not establish equivalence for all splits or merges. Absent or discontinued options remain unresolved until a source confirms them. Product distributions, data vintages and uneven narrative opt-in remain sources of bias.

Shortcut evidence. The validation ablations in reports/validation_shortcuts.json remove redaction tokens and repeated training lines; a separate form-only classifier uses length, mask count and line count. Some SVC predictions depend on redaction markers. This is sensitivity evidence, not proof that all shortcuts have been removed.

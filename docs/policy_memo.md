# Policy Memo: Limits of CFPB Complaint Data and Archived Text Modeling

## To: Consumer protection policy and supervision team
## Subject: Proper interpretation of local CFPB trends and narrative-model results

### Recommendation

Use the current structured-data dashboard only for exploratory review of published complaint counts and issue-category shares. The historical narrative classifier is a research baseline for archived CFPB `Issue` labels, not an operational decision tool. Neither output supports legal determinations, enforcement decisions, company rankings, or estimates of market-wide consumer harm.

### Two distinct data scopes

1. **Current structured-data trends:** CFPB's current Consumer Complaint Database schema has no narrative field. The pipeline computes full-source monthly counts and shares through the snapshot date, with a maturity cutoff.
2. **Historical narrative classifier:** A separate official Narratives Archive export set contains usable narratives, dates, Complaint IDs, and Issue labels. Selected batches are discontinuous. The model trains through 2025-10, validates on 2025-11–12, and tests through 2026-08-14. It is not evaluated on later narratives or current structured records.

The archive manifest records source batches, actual eligible counts, missingness, coverage, taxonomy changes, and duplicate checks. The model card and metrics JSON report the evaluation, including the substantial Other class and temporal distribution shift.

### What the narrative evaluation supports

The tested TF-IDF/logistic-regression baseline attained 0.6294 accuracy, 0.3939 macro-F1, and 0.6236 weighted-F1 on 18,215 final-test rows, versus a training-majority baseline with 0.0340 accuracy and 0.0060 macro-F1. This is a result on the selected historical archive sample and its reduced training-derived taxonomy only. About 50.3% of test rows map to the heterogeneous Other class, compared with about 15.8% of training. The poor test majority-baseline result reflects strong temporal label shift; these results must not be generalized without per-class review.

CFPB `Issue` is not adjudicated ground truth, and no human label audit was performed. Model scores are uncalibrated. The model has not been tested on post-2026-08-14 narratives or deployed.

### What the data do not establish

CFPB explains that complaints are published after company response and confirmation of a commercial relationship, or after 15 days, whichever comes first. The archive does not provide a per-record public release timestamp. CFPB also cautions that complaint data are not representative of all marketplace experiences. Therefore:

- Complaint totals and shares are not estimates of market-wide incidence or prevalence.
- An increase is not proof of increased harm; a decrease is not proof a problem was resolved.
- `Issue` is an operational complaint category, not an adjudicated legal or causal label.
- An exploratory candidate is not a verified incident or finding about a company.
- Historical model scores do not establish quality on current or future complaint text.
- Current structured-data coverage after the text cutoff does not extend model training or validation.

### Recommended protocol

1. Preserve archive checksums, retrieval times, source schema, coverage, and taxonomy changes with every model run.
2. Review exact and approximate duplicate leakage results, including the LSH bucket exclusions.
3. Audit label quality with blinded human review before operational use; do not treat source Issue labels as ground truth.
4. For any future text period, create a new authorized dataset and predeclare chronological validation and holdout boundaries.
5. Require analyst review and independent corroboration before escalating any trend candidate or model prediction.
6. Keep structured trend coverage and archived text-model coverage separate in reporting and interfaces.

### Decision

The deliverable is a local source-and-trend exploration tool plus a historical archived-text baseline. It is not a narrative-classification product for current complaints. No publication or deployment is included.

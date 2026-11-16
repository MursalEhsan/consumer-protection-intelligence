# Remediation log

## Cleanup
Current state and defects. Development handoffs are tracked. PR #1 adds full-source year-over-year comparisons with null handling and candidate counts. Review the head and run tests before integration. gh and Docker are absent locally.

Changes and evidence. Copied the two handoffs outside the checkout, removed the tracked copies, and ignored docs/development/. No tracked notebooks found. Reviewed PR #1 and ran the tests at its exact head (19 passed). Requested a history-preserving merge. Manual repository description: "CFPB complaint trends and historical narrative classification with reproducible audits." Topics: consumer-protection, data-science, nlp, cfpb, risk-analytics.

## Historical classifier audit
Current state and defects. Read the audit, model card and training code. The training-majority comparator measures a deployable constant policy; the retrospective test majority is an oracle diagnostic. The report does not trace both to executable confusion-matrix arithmetic. Prior inspection before filtering compromises the holdout. Bounded SimHash skips oversized buckets and short texts. Changing label frequencies and repeated templates can distort evaluation. Redaction tokens, boilerplate and length are potential shortcuts; their effect is unmeasured.

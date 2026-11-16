# Fresh historical evaluation

Frozen model: tfidf_svc. Accuracy difference from retrospective test-majority oracle: 21.49 percentage points.

| Model | Accuracy | Macro F1 | Named accuracy | Other accuracy |
|---|---:|---:|---:|---:|
| majority | 0.3405 | 0.0462 | 0.4087 | 0.0000 |
| stratified | 0.2053 | 0.0919 | 0.2199 | 0.1327 |
| tfidf_logistic | 0.5384 | 0.2247 | 0.4929 | 0.7655 |
| tfidf_svc | 0.5554 | 0.3951 | 0.5230 | 0.7168 |
| minilm_logistic | 0.5229 | 0.3882 | 0.4965 | 0.6549 |

[Full metrics, paired test, bootstrap intervals, class order, test hash and run commit](metrics.json). Row-level bootstrap assumes independence after approximate deduplication. This earlier retrospective period does not establish current performance.

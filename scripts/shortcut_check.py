"""Validation-only sensitivity to text form, using the existing frozen SVC."""

import json
import re
from collections import Counter
from pathlib import Path
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from fresh_data import DuplicateFilter, ROOT, TEXT, load_split
from fresh_eval import targets


def form(s):
    return [np.log1p(len(s)), s.lower().count("xxxx"), s.count("\n")]


def main(directory):
    filt = DuplicateFilter()
    train = filt.apply(load_split(directory, "train"))
    val = filt.apply(load_split(directory, "validation"))
    labels = targets(val)
    clf = LogisticRegression(max_iter=500, random_state=427).fit(
        train[TEXT].map(form).tolist(), targets(train)
    )
    lines = Counter(
        line.strip().casefold()
        for s in train[TEXT]
        for line in set(s.splitlines())
        if len(line.strip()) >= 30
    )
    common = {k for k, n in lines.items() if n >= 5}
    model = joblib.load(ROOT / "output/fresh/frozen.joblib")[0]["tfidf_svc"]
    raw = model.predict(val[TEXT])
    out = {}
    for name, pred in {
        "original": raw,
        "redaction_mask_removed": model.predict(
            val[TEXT].map(lambda s: re.sub(r"\bx{2,}\b", " ", s, flags=re.I))
        ),
        "repeated_training_lines_removed": model.predict(
            val[TEXT].map(
                lambda s: "\n".join(line for line in s.splitlines() if line.strip().casefold() not in common)
            )
        ),
        "length_redaction_and_line_count_only": clf.predict(val[TEXT].map(form).tolist()),
    }.items():
        out[name] = {
            "accuracy": accuracy_score(labels, pred),
            "macro_f1": f1_score(labels, pred, average="macro"),
            "changed_vs_original": int((pred != raw).sum()),
        }
    (ROOT / "reports/validation_shortcuts.json").write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    import sys

    main(Path(sys.argv[1]))

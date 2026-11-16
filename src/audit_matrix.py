"""Reconcile the archived evaluation without loading complaint text or refitting."""

import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def summarize(matrix: np.ndarray, other: int) -> dict:
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    hits = matrix.diagonal()
    precision = np.divide(hits, predicted, out=np.zeros(len(hits)), where=predicted > 0)
    recall = hits / support
    f1 = 2 * hits / (support + predicted)
    size = int(support.sum())
    return {
        "rows": size,
        "correct": int(hits.sum()),
        "accuracy": float(hits.sum() / size),
        "test_majority_oracle_accuracy": float(support.max() / size),
        "accuracy_difference": float((hits.sum() - support.max()) / size),
        "macro_f1": float(f1.mean()),
        "weighted_f1": float(np.average(f1, weights=support)),
        "named_accuracy": float((hits.sum() - hits[other]) / (size - support[other])),
        "other_accuracy": float(recall[other]),
        "precision_by_class": precision.tolist(),
        "recall_by_class": recall.tolist(),
    }


def main() -> None:
    section = (
        (ROOT / "EVALUATION_AUDIT.md").read_text().split("## Full-test confusion matrix")[1].split("\n## ")[0]
    )
    labels = re.findall(r"^\| \d+ \| (.*?) \|$", section, re.M)
    rows = re.findall(r"^\| \*\*(\d+)\*\* \| ([\d, |]+)\|$", section, re.M)
    if [int(i) for i, _ in rows] != list(range(len(labels))):
        raise ValueError("Matrix and class list disagree")
    matrix = np.array(
        [[int(n.strip().replace(",", "")) for n in row.split("|") if n.strip()] for _, row in rows]
    )
    if matrix.shape != (len(labels), len(labels)):
        raise ValueError("Matrix must be square")
    other = labels.index("Other / outside selected training taxonomy")
    result = summarize(matrix, other)
    result["class_order"] = labels
    result["scope"] = "Previously inspected historical sample; retrospective test-majority comparator"
    (ROOT / "reports/historical_matrix_audit.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

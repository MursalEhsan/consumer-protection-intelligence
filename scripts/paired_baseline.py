"""Recover the exact paired test against a constant classifier from saved metrics."""

import json
from pathlib import Path
from scipy.stats import binomtest

OUT = Path(__file__).resolve().parents[1] / "reports"


def integer_count(value: float) -> int:
    n = round(value)
    if abs(value - n) > 1e-7:
        raise ValueError("Metric does not reconcile to whole cases")
    return n


def main() -> None:
    result = json.loads((OUT / "metrics.json").read_text())
    selected = json.loads((OUT / "frozen_choices.json").read_text())["best"]
    n = result["rows"]
    majority = result["models"]["majority"]
    index = majority["recall"].index(1.0)
    model = result["models"][selected]
    constant_hits = integer_count(n * majority["accuracy"])
    overlap = integer_count(model["recall"][index] * constant_hits)
    wins = integer_count(n * model["accuracy"]) - overlap
    losses = constant_hits - overlap
    details = {
        "class": result["classes"][index],
        "strongest_constant_by_test_accuracy": majority["accuracy"]
        == result["test_majority_oracle_accuracy"],
        "model_only_correct": wins,
        "baseline_only_correct": losses,
        "both_correct": overlap,
        "p_exact_two_sided": binomtest(wins, wins + losses).pvalue,
    }
    (OUT / "paired_majority.json").write_text(json.dumps(details, indent=2) + "\n")


if __name__ == "__main__":
    main()

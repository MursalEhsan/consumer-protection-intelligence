"""Exercise production TF-IDF/SVC training, calibration and a temporal scoring pass."""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from scipy.special import softmax
from linear_training import calibrate, make_text_model

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config/split.yaml").read_text())
    d = pd.read_parquet(ROOT / "tests/fixtures/synthetic_embeddings.parquet")
    dates = sorted(d["Date received"].unique())
    train, val, test = [
        d[d["Date received"] == date].sample(frac=1, random_state=cfg["seed"]) for date in dates
    ]
    labels = sorted(train.Issue.unique())
    model = make_text_model("tfidf_svc", cfg["seed"])
    model.fit(train.synthetic_text, train.Issue.map(labels.index))
    scores = model.decision_function(val.synthetic_text)
    temp, threshold = calibrate(
        scores,
        model.predict(val.synthetic_text),
        val.Issue.map(labels.index).to_numpy(),
        cfg["thresholds"],
        cfg["validation_min_precision"],
    )
    probs = softmax(model.decision_function(test.synthetic_text) / temp, axis=1)
    if not np.allclose(probs.sum(1), 1) or not np.isfinite(probs).all():
        raise ValueError("Invalid fixture probabilities")
    result = {
        "scope": "Invented smoke fixture only",
        "classes": labels,
        "threshold": threshold,
        "temperature": temp,
        "rows": len(test),
        "accepted": int((probs.max(1) >= threshold).sum()),
    }
    out = ROOT / "output/demo"
    out.mkdir(parents=True, exist_ok=True)
    (out / "fixture_model.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Synthetic temporal classifier, calibration and abstention smoke passed.")


if __name__ == "__main__":
    main()

"""Inference for the numeric-only release asset. Loading disallows Python pickles."""

import hashlib
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.special import softmax
from sklearn.feature_extraction.text import TfidfVectorizer


class PortableModel:
    def __init__(self, path: Path):
        with np.load(path, allow_pickle=False) as d:
            self.weights = d["weights"]
            self.idf = d["idf"]
            self.intercept = d["intercept"]
            self.classes = d["classes"]
            self.temperature = float(d["temperature"])
            self.threshold = float(d["threshold"])
            self.index = {k: i for i, k in enumerate(d["vocabulary_sha256"].tolist())}
        self.analyze = TfidfVectorizer(ngram_range=(1, 2)).build_analyzer()

    def predict(self, text: str) -> tuple[str, float]:
        counts = Counter(
            self.index.get(hashlib.sha256(term.encode()).hexdigest().encode()) for term in self.analyze(text)
        )
        counts.pop(None, None)
        if not counts:
            return "abstain", 0.0
        indices = list(counts)
        v = (1 + np.log(list(counts.values()))) * self.idf[indices]
        scores = self.weights[:, indices] @ (v / np.linalg.norm(v)) + self.intercept
        p = softmax(scores / self.temperature)
        i = int(p.argmax())
        return (str(self.classes[i]) if p[i] >= self.threshold else "abstain"), float(p[i])

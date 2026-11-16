"""Feature extraction and validation calibration shared by the fixture and archive."""

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import softmax
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.svm import LinearSVC


def make_text_model(name: str, seed: int) -> Pipeline:
    clf = (
        LinearSVC(random_state=seed)
        if name == "tfidf_svc"
        else LogisticRegression(max_iter=500, random_state=seed)
    )
    return make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True), clf)


def calibrate(
    scores: np.ndarray, pred: np.ndarray, y: np.ndarray, cuts: list[float], target: float
) -> tuple[float, float]:
    k = len(y) // 2
    opt = minimize_scalar(
        lambda t: -np.log(softmax(scores[:k] / t, axis=1)[np.arange(k), y[:k]].clip(1e-12)).mean(),
        bounds=(0.1, 10),
        method="bounded",
    )
    temp = float(opt.x)
    prob = softmax(scores[k:] / temp, axis=1)
    for cutoff in cuts:
        keep = prob.max(1) >= cutoff
        if keep.any() and np.mean(pred[k:][keep] == y[k:][keep]) >= target:
            return temp, cutoff
    return temp, 1.01

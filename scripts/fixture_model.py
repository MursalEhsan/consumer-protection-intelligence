"""Exercise narrative vectorization and prediction using invented sentences only."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC


def main() -> None:
    model = make_pipeline(TfidfVectorizer(ngram_range=(1, 2)), LinearSVC(random_state=427))
    model.fit(
        [
            "demo card charged twice",
            "demo card duplicate charge",
            "demo transfer missing",
            "demo transfer delayed",
        ],
        ["billing", "billing", "transfer", "transfer"],
    )
    if model.predict(["demo duplicate card charge", "demo transfer"]).tolist() != ["billing", "transfer"]:
        raise AssertionError("Unexpected synthetic fixture predictions")
    print("Synthetic narrative smoke test passed. No performance estimate.")


if __name__ == "__main__":
    main()

"""Match rolling semantic clusters across time using only earlier centroids."""

import re
import numpy as np
import pandas as pd
import yaml
from scipy.optimize import linear_sum_assignment
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from sklearn.preprocessing import normalize
from hdbscan import HDBSCAN
from umap import UMAP
from detector import ROOT, forecast, tail
from fresh_data import TEXT

CFG = yaml.safe_load((ROOT / "config/clusters.yaml").read_text())


def run() -> None:
    folder = ROOT / "output/clusters"
    d = pd.read_parquet(folder / "sample.parquet")
    vec = np.load(folder / "embedding.npy")
    dates = pd.to_datetime(d["Date received"]).dt.to_period("M")
    # Fixed public vocabulary prevents export of names or identifiers in keyword labels.
    terms = sorted(
        set(
            re.findall(
                r"[a-z]{3,}", " ".join(pd.read_csv(ROOT / "docs/backtest_events.csv").issue.unique()).lower()
            )
        )
        - ENGLISH_STOP_WORDS
    )
    cnt = CountVectorizer(vocabulary=terms)
    rows = []
    for product, sub in d.groupby("Product"):
        previous = {}
        histories = {}
        seq = 0
        for m in pd.period_range(dates.loc[sub.index].min(), dates.loc[sub.index].max(), freq="M"):
            ix = sub.index[dates.loc[sub.index].between(m - CFG["window_months"] + 1, m)]
            if len(ix) < CFG["minimum_window_size"] or not (dates.loc[ix] == m).any():
                previous = {}
                continue
            coords = UMAP(
                n_neighbors=min(10, len(ix) - 1),
                n_components=2,
                random_state=CFG["seed"],
                n_jobs=1,
                n_epochs=60,
            ).fit_transform(vec[ix])
            labels = HDBSCAN(min_cluster_size=CFG["minimum_cluster_size"]).fit_predict(coords)
            ids = sorted(set(labels) - {-1})
            if not ids:
                previous = {}
                continue
            centers = normalize(np.stack([vec[ix[labels == i]].mean(axis=0) for i in ids]))
            prev = list(previous)
            matches = {}
            if prev:
                sims = centers @ np.stack(list(previous.values())).T
                a, b = linear_sum_assignment(-sims)
                matches = {i: prev[j] for i, j in zip(a, b) if sims[i, j] >= CFG["cosine_link"]}
            previous = {}
            term_counts = np.stack(
                [np.asarray(cnt.transform(sub.loc[ix[labels == i], TEXT]).sum(0)).ravel() for i in ids]
            )
            idf = np.log1p(term_counts.sum(1).mean() / term_counts.sum(0).clip(1))
            for k, i in enumerate(ids):
                key = matches.get(k)
                new = key is None
                if new:
                    seq += 1
                    key = seq
                previous[key] = centers[k]
                active = ix[(labels == i) & (dates.loc[ix].values == m)]
                n = len(active)
                history = histories.setdefault(key, {})
                previous_counts = np.array([history.get(m - j, 0) for j in range(36, 0, -1)])
                growth = False
                if len(history) >= 36 and previous_counts.reshape(3, 12).sum(0).min() > 0:
                    mu, a = forecast(previous_counts)
                    growth = tail(n, mu, a) < 0.01
                history[m] = n
                if n == 0:
                    continue
                relevance = term_counts[k] / max(1, term_counts[k].sum()) * idf
                words = [terms[j] for j in np.argsort(-relevance)[:4] if relevance[j] > 0]
                rows.append(
                    (
                        str(m),
                        product,
                        key,
                        n,
                        str(sub.loc[active, "Issue"].mode().iloc[0]),
                        " ".join(words),
                        new,
                        growth,
                    )
                )
    pd.DataFrame(
        rows,
        columns=["month", "product", "cluster", "sample_count", "modal_issue", "keywords", "new", "growth"],
    ).to_csv(ROOT / "reports/clusters.csv", index=False)


if __name__ == "__main__":
    run()

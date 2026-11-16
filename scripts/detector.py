"""Retrospective monthly screening; counts are latest-snapshot vintages."""

import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from scipy.stats import nbinom, poisson
from statsmodels.api import GLM, families
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config/detector.yaml").read_text())


def aggregate(df):
    cross = pd.read_csv(ROOT / "sql/issue_crosswalk.csv")
    df = df.merge(
        cross,
        left_on=["Product", "Issue"],
        right_on=["product", "raw_issue"],
        how="left",
        validate="many_to_one",
    )
    df["issue_key"] = df.stable_issue.fillna(df.Issue)
    with sqlite3.connect(":memory:") as con:
        df[["month", "Product", "issue_key", "count"]].to_sql("mapped_counts", con, index=False)
        return pd.read_sql_query((ROOT / "sql/within_product.sql").read_text(), con)


def forecast(y):
    """Conditional NB2 GLM with log link; Poisson fallback at zero overdispersion."""
    w = len(y)
    months = np.arange(w + 1) % 12
    x = np.column_stack([np.ones(w + 1), np.arange(w + 1) / w, np.eye(12)[months, 1:]])
    fit = GLM(y, x[:-1], family=families.Poisson()).fit(maxiter=60)
    mu = fit.fittedvalues
    alpha = max(0.0, float(np.sum((y - mu) ** 2 - y) / max(np.sum(mu**2), 1)))
    if alpha > 1e-8:
        fit = GLM(y, x[:-1], family=families.NegativeBinomial(alpha=alpha)).fit(maxiter=60)
    pred = float(fit.predict(x[-1:])[0])
    # Moment-match predictive variance, including estimated coefficient uncertainty.
    var = pred + (alpha + max(0, float(x[-1] @ fit.cov_params() @ x[-1]))) * pred**2
    a = max(0, (var - pred) / max(pred**2, 1e-20))
    return pred, a


def tail(count, mu, a):
    if a < 1e-8:
        return poisson.sf(count - 1, mu)
    return nbinom.sf(count - 1, 1 / a, 1 / (1 + a * mu))


def replay(raw):
    from cfpb_pipeline import find_emerging_issue_candidates

    total = raw.groupby("month")["count"].sum()
    overall = (
        raw.groupby(["month", "Issue"])["count"]
        .sum()
        .reset_index()
        .rename(columns={"month": "complaint_month", "Issue": "issue", "count": "complaint_count"})
    )
    overall["monthly_denominator"] = overall.complaint_month.map(total)
    overall["complaint_share"] = overall.complaint_count / overall.monthly_denominator
    legacy = find_emerging_issue_candidates(overall, raw.month.max())
    legacy_keys = set(zip(legacy.complaint_month.astype(str), legacy.issue))
    data = aggregate(raw)
    records = []
    for (product, issue), group in data.groupby(["Product", "issue_key"]):
        totals = raw[raw.Product == product].groupby("month")["count"].sum()
        idx = pd.period_range(group.month.min(), raw.month.max(), freq="M").astype(str)
        y = group.set_index("month").issue_count.reindex(idx, fill_value=0)
        for t in range(CFG["window"], len(y)):
            month = y.index[t]
            if month < CFG["start"] or not totals.get(month, 0):
                continue
            history = y.iloc[t - CFG["window"] : t]
            if (
                not history.index.isin(totals.index).all()
                or history.mean() < CFG["min_history_volume"]
                or history.groupby(np.arange(len(history)) % 12).sum().min() == 0
            ):
                continue
            mu, a = forecast(history.to_numpy())
            if not np.isfinite(mu + a):
                raise ValueError("Invalid count forecast")
            v = int(y.iloc[t])
            std = history.std()
            zlim = float(history.mean() + CFG["z"] * std)
            ewm = float(history.ewm(alpha=CFG["ewma_alpha"], adjust=False).mean().iloc[-1] + CFG["z"] * std)
            records.append(
                (
                    month,
                    product,
                    issue,
                    v,
                    v / totals[month],
                    mu,
                    a,
                    tail(v, mu, a),
                    zlim,
                    ewm,
                    (month, issue) in legacy_keys,
                )
            )
    df = pd.DataFrame(
        records,
        columns=[
            "month",
            "product",
            "issue",
            "count",
            "share",
            "expected",
            "dispersion",
            "p",
            "z_limit",
            "ewma_limit",
            "legacy",
        ],
    )
    df["q"] = df.groupby("month").p.transform(lambda p: multipletests(p, method="fdr_bh")[1])
    df["glm"] = False
    for _, g in df.groupby(["product", "issue"]):
        recent = g.q.lt(CFG["family_alpha"])
        adjacent = g.month.map(lambda m: pd.Period(m, "M").ordinal).diff().eq(1)
        df.loc[g.index, "glm"] = recent & recent.shift(fill_value=False) & adjacent
    df["rolling_z"] = df["count"] > df.z_limit
    df["ewma"] = df["count"] > df.ewma_limit
    return df


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    df = replay(pd.read_parquet(ROOT / "reports/product_monthly.parquet"))
    df.to_parquet(ROOT / "reports/detector_replay.parquet", index=False)

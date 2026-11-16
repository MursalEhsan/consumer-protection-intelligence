"""Aggregate-only viewer with hash-verified historical model inference."""

import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd
import streamlit as st
from portable_model import PortableModel

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports"


@st.cache_resource
def load_model() -> PortableModel:
    config = json.loads((ROOT / "config/model_asset.json").read_text())
    with tempfile.NamedTemporaryFile(suffix=".npz") as f:
        with urllib.request.urlopen(config["url"], timeout=30) as response:
            f.write(response.read())
        f.flush()
        if hashlib.sha256(Path(f.name).read_bytes()).hexdigest() != config["sha256"]:
            raise ValueError("Release asset failed checksum verification")
        return PortableModel(Path(f.name))


st.set_page_config(page_title="Consumer complaint review", layout="wide")
st.title("Consumer complaint review")
trends, watch, model, methods = st.tabs(
    ["Trends by product", "Watchlist", "Classifier demo", "Methodology and limitations"]
)
with trends:
    d = pd.read_parquet(OUT / "product_monthly.parquet")
    product = st.selectbox("Product", sorted(d.Product.unique()))
    subset = d[d.Product == product]
    issue = st.selectbox(
        "Recorded issue", subset.groupby("Issue")["count"].sum().sort_values(ascending=False).index
    )
    series = subset[subset.Issue == issue].set_index("month")
    st.line_chart(
        series.share.rename("Share within product"),
        x_label="Complaint month",
        y_label="Fraction of published complaints",
    )
    st.caption(
        "Missing issue months have no plotted observations. Products can change definitions over time."
    )
with watch:
    q = pd.read_parquet(OUT / "watchlist.parquet")
    date = json.loads((OUT / "product_monthly.json").read_text())["last_month"]
    st.subheader(f"Review queue for {date}")
    if q.empty:
        st.write("The retained screening rule flagged no issues in this month.")
    else:
        st.dataframe(q, hide_index=True)
    st.dataframe(pd.read_csv(OUT / "backtest_table.csv"), hide_index=True)
with model:
    st.write(
        "The classifier was evaluated on historical archived narratives. Use fictional text for this demonstration."
    )
    narrative = st.text_area("Complaint description", max_chars=5000)
    if st.button("Classify", disabled=not narrative.strip()):
        try:
            label, score = load_model().predict(narrative)
            st.write(f"Decision: {label}")
            if score:
                st.metric("Temperature-calibrated confidence", f"{score:.1%}")
            else:
                st.write("No vocabulary overlap. Abstained without scoring.")
        except (OSError, ValueError) as exc:
            st.error(f"Model unavailable: {exc}")
with methods:
    st.markdown((ROOT / "docs/client_brief.md").read_text())
    st.markdown((OUT / "classifier_eval.md").read_text().split("[Full metrics")[0])
    st.write(
        "The selected classifier abstains below its validation-frozen threshold. Historical probabilities may drift."
    )

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_DIR / "output"
MANIFEST_PATH = PROJECT_DIR / "CFPB_DATA_MANIFEST.json"
NARRATIVE_MODEL_PATH = PROJECT_DIR / "complaint_narrative_tfidf_logreg.joblib"
NARRATIVE_METRICS_PATH = OUTPUT_DIR / "cfpb_narrative_model_metrics.json"
NARRATIVE_ARCHIVE_PAGE = (
    "https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/"
    "cfpb-consumer-complaint-database-narratives-archive/"
)
TRENDS_PATH = OUTPUT_DIR / "issue_trends_monthly.csv"
CANDIDATES_PATH = OUTPUT_DIR / "emerging_issue_candidates.csv"

st.set_page_config(page_title="CFPB Complaint Analysis", layout="wide")
st.title("CFPB Complaint Analysis")
st.caption(
    "Local source and trend exploration alongside a separately trained classifier "
    "for narratives in CFPB's historical archive."
)

if not MANIFEST_PATH.exists() or not TRENDS_PATH.exists():
    st.info("Trend outputs are not available yet. Run `make run` from the project directory.")
    st.stop()

manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
summary = manifest["dataset_summary"]
maturity = manifest.get("evaluation_maturity", {})
trends_tab, narrative_tab = st.tabs(
    ["Current structured-data trends", "Archived narrative classifier"]
)

with trends_tab:
    metrics = st.columns(4)
    metrics[0].metric("Rows in source archive", f"{summary['row_count']:,}")
    metrics[1].metric("Local sample rows", f"{summary['sample_row_count']:,}")
    metrics[2].metric(
        "Complaint dates",
        f"{summary['earliest_complaint_date']} to {summary['latest_complaint_date']}",
    )
    metrics[3].metric(
        "Latest complete month", maturity.get("last_complete_month", "Not calculated")
    )

    trends = pd.read_csv(TRENDS_PATH)
    if trends.empty:
        st.warning("No complete-month trend data is available.")
    else:
        trends["complaint_month"] = trends["complaint_month"].astype(str)
        months = sorted(trends["complaint_month"].unique())
        default_start = max(0, len(months) - 36)
        selected_months = st.select_slider(
            "Complete-month range",
            options=months,
            value=(months[default_start], months[-1]),
        )
        filtered = trends[
            trends["complaint_month"].between(selected_months[0], selected_months[1])
        ].copy()

        recent = filtered.groupby("issue", as_index=False)["complaint_count"].sum()
        default_issues = recent.nlargest(8, "complaint_count")["issue"].tolist()
        issues = st.multiselect(
            "Issue categories",
            options=sorted(filtered["issue"].unique()),
            default=default_issues,
        )
        selected = filtered[filtered["issue"].isin(issues)]

        st.subheader("Monthly share of CFPB complaints")
        st.caption(
            "Shares use all complaints with a valid received date in each month as the denominator. "
            "The complete-month cutoff applies a 15-day publication-maturity rule."
        )
        if selected.empty:
            st.info("Choose at least one issue category to display trends.")
        else:
            share_chart = selected.pivot(
                index="complaint_month", columns="issue", values="complaint_share"
            ).sort_index()
            st.line_chart(share_chart)

        with st.expander("Counts and denominators"):
            st.dataframe(
                selected.sort_values(
                    ["complaint_month", "complaint_count"], ascending=[False, False]
                ),
                hide_index=True,
                width="stretch",
            )

        st.subheader("Exploratory emerging-issue candidates")
        st.caption(
            "Candidates use a same-calendar-month historical comparison. They are prompts for "
            "analyst review, not confirmed incidents, causal findings, or evidence of harm."
        )
        if CANDIDATES_PATH.exists():
            candidates = pd.read_csv(CANDIDATES_PATH)
            if candidates.empty:
                st.write("No candidates met the current exploratory threshold.")
            else:
                st.dataframe(candidates, hide_index=True, width="stretch")
        else:
            st.info("Candidate output is missing. Run `make run` to regenerate it.")

        with st.expander("Structured source and limitations"):
            st.write(f"Source: {manifest.get('source', 'CFPB Consumer Complaint Database')}")
            st.write(f"Retrieved: {manifest.get('retrieval_timestamp_utc', 'Not recorded')}")
            st.write(
                "This current structured-data snapshot contains complaint metadata and issue "
                "categories, not narratives. CFPB notes that complaints are published after the "
                "company responds and confirms a commercial relationship, or after 15 days, whichever "
                "comes first, and that complaint data are not representative of all consumer "
                "experiences."
            )

with narrative_tab:
    st.subheader("Historical CFPB complaint narratives")
    st.warning(
        "This model uses a separate, discontinuous set of official archive exports. It was trained "
        "through 2025-10, validated on 2025-11–2025-12, and held out on 2026-01–2026-08-14. "
        "It is not evaluated on later narratives or the current structured-data trend snapshot."
    )
    st.write(
        "Only enter text you are authorized to process. Input is classified locally for this "
        "request and is not written to the project dataset or model artifacts. The form clears "
        "after submission."
    )

    if not NARRATIVE_METRICS_PATH.exists() or not NARRATIVE_MODEL_PATH.exists():
        st.error(
            "The archived narrative model or evaluation metrics are unavailable. "
            "Run `make narrative-model` locally to generate them."
        )
    else:
        model_metrics = json.loads(
            NARRATIVE_METRICS_PATH.read_text(encoding="utf-8")
        )
        test = model_metrics["evaluation"]["test"]
        model_result = test["tfidf_logistic_regression"]
        baseline_result = test["baseline_most_frequent"]
        metric_columns = st.columns(3)
        metric_columns[0].metric(
            "Test accuracy",
            f"{model_result['accuracy']:.3f}",
            delta=(
                f"{(model_result['accuracy'] - baseline_result['accuracy']) * 100:+.2f} "
                "percentage points vs baseline"
            ),
        )
        metric_columns[1].metric("Test macro-F1", f"{model_result['macro_f1']:.3f}")
        metric_columns[2].metric("Test rows", f"{model_result['rows']:,}")
        st.caption(
            "Chronological held-out test; issue taxonomy selected using training labels only. "
            "The training-majority baseline predicts `Incorrect information on your report` "
            "(the most frequent mapped training label). The test distribution has a high "
            "Other/out-of-taxonomy share; scores are not calibrated."
        )
        with st.expander("Validation/test evaluation details"):
            for split_name in ("validation", "test"):
                split_result = model_metrics["evaluation"][split_name]
                st.markdown(f"**{split_name.title()}**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "model": model_name.replace("_", " "),
                                "accuracy": result["accuracy"],
                                "macro-F1": result["macro_f1"],
                                "weighted-F1": result["weighted_f1"],
                                "rows": result["rows"],
                            }
                            for model_name, result in split_result.items()
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
            st.write("Selected training taxonomy:")
            st.write(model_metrics["taxonomy"]["selected_issue_labels"])

        with st.form("archived_narrative_inference", clear_on_submit=True):
            narrative = st.text_area(
                "Complaint narrative",
                max_chars=20_000,
                help="Text is sent only to the locally loaded model; do not enter sensitive personal data.",
            )
            submitted = st.form_submit_button("Classify locally")
        if submitted:
            if not narrative.strip():
                st.error("Enter nonblank narrative text.")
            else:
                local_model = joblib.load(NARRATIVE_MODEL_PATH)
                prediction = local_model.predict([narrative])[0]
                st.success(f"Predicted archive Issue category: {prediction}")
                if hasattr(local_model, "predict_proba"):
                    probabilities = local_model.predict_proba([narrative])[0]
                    classes = local_model.classes_
                    ranked = sorted(
                        zip(classes, probabilities), key=lambda item: item[1], reverse=True
                    )[:3]
                    st.caption("Top model scores (uncalibrated; not operational confidence)")
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {"Issue category": label, "Model score": float(score)}
                                for label, score in ranked
                            ]
                        ),
                        hide_index=True,
                        width="stretch",
                    )

    with st.expander("Archive provenance and limits"):
        st.write(
            "The source is the [official CFPB Consumer Complaint Database Narratives Archive]"
                f"({NARRATIVE_ARCHIVE_PAGE}). "
            "Selected exports have gaps, including the long gap from 2018-04 to 2024-11. The classifier "
            "predicts a bounded `Issue` taxonomy derived from the training sample; other source labels "
            "map to an Other category. Source labels are not adjudicated ground truth."
        )
        st.write(
            "Current structured trends use a separate CFPB database snapshot through "
            f"{summary['latest_complaint_date']}. Do not interpret that later date as text-model "
            "coverage or validation."
        )

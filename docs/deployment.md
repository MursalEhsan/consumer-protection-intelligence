# Deploy the aggregate viewer

A hosted app URL has not been verified. This session has GitHub authorization but no authenticated Streamlit Community Cloud or Hugging Face Spaces publisher session.

1. Sign in to Streamlit Community Cloud at https://share.streamlit.io/ and choose Create app.
2. Select MursalEhsan/consumer-protection-intelligence and the remediation/evidence-audit branch (or the merged release tag's branch).
3. Set the entry point to src/public_app.py and select Python 3.12 in Advanced settings. Deploy.
4. Open all four tabs. Check the watchlist period against reports/product_monthly.json. Classify a fictional statement and a string of out-of-vocabulary tokens. Confirm the latter abstains.
5. Copy the verified public URL into the README.

Only the numeric model asset is fetched on first inference. The published GitHub asset is checksum-verified against config/model_asset.json. The app does not write or retain submitted text. The cloud host controls its own infrastructure logs.

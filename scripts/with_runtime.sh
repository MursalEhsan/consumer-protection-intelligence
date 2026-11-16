#!/bin/sh
set -eu
if command -v python3.12 >/dev/null; then py=python3.12; else py=python3; fi
if python3 -c 'import pandas, sklearn, pyarrow, matplotlib, statsmodels, yaml, streamlit, umap, hdbscan' >/dev/null 2>&1; then
  exec python3 "$@"
fi
if ! test -f .venv/.installed || test requirements.lock -nt .venv/.installed; then
  "$py" -m venv .venv
  .venv/bin/python -m pip install -r requirements.lock
  touch .venv/.installed
fi
exec .venv/bin/python "$@"

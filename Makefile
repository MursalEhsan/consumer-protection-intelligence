.PHONY: setup run test report clean source-assessment refresh-data narrative-model app

setup:
	python3 -m pip install -r requirements.txt

run:
	python3 src/cfpb_pipeline.py

refresh-data:
	python3 src/cfpb_pipeline.py --refresh-source --refresh-sample

source-assessment:
	python3 src/cfpb_source_assessment.py

narrative-model:
	python3 scripts/fixture_model.py

app:
	streamlit run src/public_app.py --server.address=127.0.0.1 --server.headless=true --server.port=8501

test:
	python3 -m unittest discover -s tests -v

report: run
	python3 src/generate_report.py

clean:
	rm -f complaints_warehouse.db

.PHONY: demo
demo: narrative-model
	PYTHONPATH=src:scripts python3 -c "from pathlib import Path; import pandas as pd; from detector import replay; x=replay(pd.read_parquet('tests/fixtures/monthly.parquet')); target=Path('output/demo'); target.mkdir(parents=True,exist_ok=True); x.to_parquet(target/'scores.parquet',index=False); assert x.glm.any(); print('Synthetic product detector smoke test passed')"

.PHONY: historical-narrative-model
historical-narrative-model:
	python3 src/cfpb_narrative_model.py

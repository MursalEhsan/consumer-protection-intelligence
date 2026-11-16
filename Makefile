.PHONY: setup run test report clean source-assessment refresh-data narrative-model app

setup:
	python3 -m pip install -r requirements.txt

run:
	python3 src/cfpb_pipeline.py
	PYTHONPATH=src:scripts python3 scripts/refresh_product.py

refresh-data:
	python3 src/cfpb_pipeline.py --refresh-source --refresh-sample

source-assessment:
	python3 src/cfpb_source_assessment.py

narrative-model:
	sh scripts/with_runtime.sh scripts/fixture_model.py

app:
	streamlit run src/public_app.py --server.address=127.0.0.1 --server.headless=true --server.port=8501

test:
	sh scripts/with_runtime.sh -m unittest discover -s tests -v

report: run
	python3 src/generate_report.py

clean:
	rm -f complaints_warehouse.db

.PHONY: demo
demo:
	PYTHONPATH=src:scripts sh scripts/with_runtime.sh scripts/demo.py

.PHONY: historical-narrative-model
historical-narrative-model:
	python3 src/cfpb_narrative_model.py

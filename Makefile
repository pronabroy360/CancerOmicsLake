VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip

.PHONY: setup test run-metadata run-metadata-strict run-metadata-strict-smoke run-download-tcga run-silver run-gold run-quality run-graph-export run-flow run-dbt test-dbt run-api run-dashboard validate-config

setup:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

validate-config:
	$(PYTHON) -m src.main validate-config --config configs/project_config.yml

run-metadata:
	$(PYTHON) -m src.main run-metadata --config configs/project_config.yml

run-metadata-strict:
	$(PYTHON) -m src.main run-metadata --config configs/project_config.yml --require-live-gdc

run-metadata-strict-smoke:
	-$(PYTHON) -m src.main run-metadata --config configs/project_config.yml --require-live-gdc --gdc-base-url http://127.0.0.1:9
	$(PYTHON) -c "import json,sys; d=json.load(open('outputs/reports/gdc_ingestion_audit.json','r',encoding='utf-8')); sys.exit(0 if d.get('source_mode')=='failed_live_required' else 1)"

run-silver:
	$(PYTHON) -m src.main run-silver --config configs/project_config.yml

run-download-tcga:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml

run-download-tcga-force-smoke:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml --force-download --max-downloads 3 --data-subdirs expression,mutations

run-gold:
	$(PYTHON) -m src.main run-gold --config configs/project_config.yml

run-quality:
	$(PYTHON) -m src.main run-quality --config configs/project_config.yml

run-graph-export:
	$(PYTHON) -m src.main run-graph-export --config configs/project_config.yml

run-flow:
	$(PYTHON) -m src.main run-flow --config configs/project_config.yml

run-dbt:
	$(VENV)/bin/dbt run --project-dir dbt --profiles-dir dbt

test-dbt:
	$(VENV)/bin/dbt test --project-dir dbt --profiles-dir dbt

run-api:
	$(PYTHON) -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py --server.port 8501

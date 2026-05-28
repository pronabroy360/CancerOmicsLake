VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip

.PHONY: setup test run-metadata run-metadata-strict run-silver run-gold run-quality run-api run-dashboard validate-config

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

run-silver:
	$(PYTHON) -m src.main run-silver --config configs/project_config.yml

run-gold:
	$(PYTHON) -m src.main run-gold --config configs/project_config.yml

run-quality:
	$(PYTHON) -m src.main run-quality --config configs/project_config.yml

run-api:
	$(PYTHON) -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py --server.port 8501

PYTHON ?= python3
PIP ?= pip3

.PHONY: setup test run-metadata run-silver run-api run-dashboard validate-config

setup:
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

validate-config:
	$(PYTHON) -m src.main validate-config --config configs/project_config.yml

run-metadata:
	$(PYTHON) -m src.main run-metadata --config configs/project_config.yml

run-silver:
	$(PYTHON) -m src.main run-silver --config configs/project_config.yml

run-api:
	$(PYTHON) -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py --server.port 8501

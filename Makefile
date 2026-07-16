VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip

# When SKIP_GMT_FETCH=1 the pathway-enrichment target will not pull the
# Reactome GMT (useful in CI / sandboxes without egress). The downstream
# analytics layer will then return its normal `skipped_missing_inputs` status.
ifeq ($(SKIP_GMT_FETCH),1)
GMT_DEP =
else
GMT_DEP = fetch-reactome-gmt
endif

RELEASE_VERSION ?= 0.1.0

.PHONY: setup test run-metadata run-metadata-strict run-metadata-strict-smoke run-download-tcga run-download-tcga-ci-smoke run-download-tcga-medium run-download-tcga-aggressive run-download-tcga-normals run-download-tcga-paired run-gtex-live run-recount3-expression run-silver run-gold run-quality run-graph-export run-graph-metrics run-evidence-confidence run-bootstrap-stability run-external-validation run-expression-statistics run-paired-expression run-consensus-candidates run-pathway-enrichment fetch-reactome-gmt run-ingestion-traceability run-demo run-demo-aggressive run-demo-check run-demo-check-strict run-flow run-flow-medium run-flow-aggressive run-dbt test-dbt run-project-completion run-research-benchmark build-fair-release run-api run-dashboard validate-config

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

run-gtex-live:
	$(PYTHON) -m src.main run-gtex --config configs/project_config.yml --force-download --sample-cap-per-tissue 50

run-download-tcga:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml

run-download-tcga-ci-smoke:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml --force-download --expression-cap-per-project 1 --mutation-cap-per-project 1 --max-downloads 6 --data-subdirs expression,mutations

run-download-tcga-medium:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml --force-download --use-medium-cap-profile --data-subdirs expression,mutations --download-workers 4

run-download-tcga-aggressive:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml --force-download --use-aggressive-cap-profile --data-subdirs expression,mutations --download-workers 8

run-download-tcga-normals:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml --force-download --expression-cap-per-project 0 --normal-expression-cap-per-project 60 --data-subdirs expression --download-workers 8

run-download-tcga-paired:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml --force-download --expression-cap-per-project 100 --data-subdirs expression --download-workers 8 --pair-tumors-to-downloaded-normals

run-download-tcga-force-smoke:
	$(PYTHON) -m src.main run-download-tcga --config configs/project_config.yml --force-download --max-downloads 3 --data-subdirs expression,mutations

run-gold:
	$(PYTHON) -m src.main run-gold --config configs/project_config.yml

run-quality:
	$(PYTHON) -m src.main run-quality --config configs/project_config.yml

run-graph-export:
	$(PYTHON) -m src.main run-graph-export --config configs/project_config.yml

run-graph-metrics:
	$(PYTHON) -m src.main run-graph-metrics --config configs/project_config.yml

run-evidence-confidence:
	$(PYTHON) -m src.main run-evidence-confidence --config configs/project_config.yml

run-bootstrap-stability:
	$(PYTHON) -m src.main run-bootstrap-stability --config configs/project_config.yml --candidates-per-cancer 500 --iterations 200 --top-k 50 --random-seed 20260710

run-external-validation:
	$(PYTHON) -m src.main run-external-validation --config configs/project_config.yml --recount3-expression-path data/silver/silver_expression_recount3.parquet --top-k 100

run-expression-statistics:
	$(PYTHON) -m src.main run-expression-statistics --config configs/project_config.yml

run-paired-expression:
	$(PYTHON) -m src.main run-paired-expression --config configs/project_config.yml

run-consensus-candidates:
	$(PYTHON) -m src.main run-consensus-candidates --config configs/project_config.yml

fetch-reactome-gmt:
	@bash scripts/fetch_reactome_gmt.sh

run-pathway-enrichment: $(GMT_DEP)
	$(PYTHON) -m src.main run-pathway-enrichment --config configs/project_config.yml

run-recount3-expression:
	$(PYTHON) -m src.main run-recount3-expression --config configs/project_config.yml --sample-cap-per-cohort 30

run-ingestion-traceability:
	$(PYTHON) -m src.main run-ingestion-traceability --config configs/project_config.yml

run-demo:
	$(PYTHON) -m src.main run-flow --config configs/project_config.yml --force-download --use-medium-cap-profile --data-subdirs expression,mutations --download-workers 4
	$(PYTHON) -m src.main run-ingestion-traceability --config configs/project_config.yml
	$(PYTHON) -m src.main run-demo-check --config configs/project_config.yml

run-demo-aggressive:
	$(PYTHON) -m src.main run-flow --config configs/project_config.yml --force-download --use-aggressive-cap-profile --data-subdirs expression,mutations --download-workers 8
	$(PYTHON) -m src.main run-ingestion-traceability --config configs/project_config.yml
	$(PYTHON) -m src.main run-demo-check --config configs/project_config.yml

run-demo-check:
	$(PYTHON) -m src.main run-demo-check --config configs/project_config.yml

run-demo-check-strict:
	$(PYTHON) -m src.main run-demo-check --config configs/project_config.yml --strict-no-stub

run-flow:
	$(PYTHON) -m src.main run-flow --config configs/project_config.yml

run-flow-medium:
	$(PYTHON) -m src.main run-flow --config configs/project_config.yml --force-download --use-medium-cap-profile --data-subdirs expression,mutations --download-workers 4

run-flow-aggressive:
	$(PYTHON) -m src.main run-flow --config configs/project_config.yml --force-download --use-aggressive-cap-profile --data-subdirs expression,mutations --download-workers 8

run-dbt:
	$(PYTHON) -m src.main run-dbt --config configs/project_config.yml

test-dbt:
	$(PYTHON) -m src.main test-dbt --config configs/project_config.yml

run-project-completion:
	$(PYTHON) -m src.main run-project-completion --config configs/project_config.yml

run-research-benchmark:
	$(PYTHON) -m src.main run-research-benchmark --config configs/project_config.yml

build-fair-release:
	$(PYTHON) -m src.main build-fair-release --config configs/project_config.yml --version $(RELEASE_VERSION)

run-api:
	$(PYTHON) -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

run-dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py --server.port 8501

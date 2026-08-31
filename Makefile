SHELL := /bin/bash
MODEL ?= qwen2.5-coder:3b
OLLAMA := .tools/ollama/Ollama.app/Contents/Resources/ollama
MODEL_STORE := $(CURDIR)/.cache/ollama/models
HARBOR := $(CURDIR)/.tools/bin/harbor
PYTHON := $(CURDIR)/.tools/uv-tools/harbor/bin/python

.PHONY: preflight model-pull model-start model-test oracle mini-swe openhands custom matrix collect report evidence test stop all

preflight:
	./scripts/preflight.sh

model-pull: model-start
	OLLAMA_MODELS="$(MODEL_STORE)" $(OLLAMA) pull $(MODEL)
	OLLAMA_MODELS="$(MODEL_STORE)" $(OLLAMA) show $(MODEL)

model-start:
	./scripts/start_model.sh

model-test:
	./scripts/test_model_endpoint.sh

oracle:
	$(PYTHON) ./scripts/run_baselines.py --harness oracle

mini-swe:
	$(PYTHON) ./scripts/run_baselines.py --harness mini-swe-agent

openhands:
	$(PYTHON) ./scripts/run_baselines.py --harness openhands

custom:
	$(PYTHON) ./scripts/run_baselines.py --harness custom

matrix:
	$(PYTHON) ./scripts/run_matrix.py

collect:
	$(PYTHON) ./scripts/collect_results.py

report:
	$(PYTHON) ./scripts/generate_progress_report.py

evidence:
	$(PYTHON) ./scripts/export_terminal_evidence.py

test:
	$(PYTHON) -m unittest discover -s tests -v

stop:
	./scripts/stop_model.sh

all: preflight model-pull model-test oracle matrix collect report evidence test stop

# AEGIS OS task entry point. Logic lives in scripts/ and tests/; keep recipes short.
.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

SHELL_SCRIPTS := $(shell git ls-files 'scripts/*')
YAML_FILES := $(shell git ls-files '*.yml' '*.yaml')

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

.PHONY: static
static: ## Repository rule tests and Python lint (runs anywhere)
	pytest -q tests/static
	ruff check .
	ruff format --check .

.PHONY: lint
lint: static ## static + shellcheck, yamllint, actionlint, gitleaks (CI or a full workstation)
	shellcheck $(SHELL_SCRIPTS)
	yamllint --strict $(YAML_FILES)
	actionlint
	gitleaks git --no-banner --redact .

.PHONY: probe
probe: ## Print environment capabilities (read-only)
	scripts/probe-env

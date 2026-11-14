# AEGIS OS task entry point. Logic lives in scripts/ and tests/; keep recipes short.
.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

SHELL_SCRIPTS := $(shell git ls-files 'scripts/*' 'image/build/*')
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

# --- Image, disk and virtual-machine targets. These need podman, access to quay.io and
# --- (for vm-test) ideally KVM. They run in GitHub Actions or on a Linux workstation.

.PHONY: image
image: ## Build the aegis-base and aegis-dev container images (B-01)
	scripts/build-image

.PHONY: disk
disk: ## Install both variants into image files under out/ (never a real disk)
	scripts/build-disk localhost/aegis-dev:latest out/disk.raw
	scripts/build-disk localhost/aegis-base:latest out/disk-base.raw

.PHONY: builder
builder: ## Build the test container (QEMU, UEFI firmware, pytest)
	scripts/build-builder

.PHONY: inventory
inventory: ## Record packages, units, privileged files and permissive domains of both images
	scripts/inventory-image

.PHONY: image-test
image-test: ## Compare the inventory with the golden manifests (B-02, B-03, B-04)
	scripts/run-image-tests

.PHONY: golden-update
golden-update: ## Accept the current inventory as the new golden manifests (review the diff!)
	scripts/update-golden

.PHONY: vm-test
vm-test: ## Boot both disk images in QEMU and run the VM tests
	scripts/run-vm-tests

.PHONY: summary
summary: ## Print the evidence collected by the last build and VM test run
	scripts/summarize-results

.PHONY: all
all: image builder inventory image-test disk vm-test ## Build, inventory, install, boot and test everything

# AEGIS OS task entry point. Logic lives in scripts/ and tests/; keep recipes short.
.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

SHELL_SCRIPTS := $(filter-out %.py,$(shell git ls-files 'scripts/*' 'image/build/*' 'local-vm/*.sh' 'image/rootfs/usr/libexec/aegis/*' 'image/rootfs-gui/usr/libexec/aegis/*' 'image/rootfs-live/usr/libexec/aegis/*' 'image/rootfs-v3/usr/libexec/aegis/*'))
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

.PHONY: inputs
inputs: ## Fetch the locked RPM inputs and verify size, SHA-256, identity, signature (P1-15)
	scripts/fetch-inputs

.PHONY: input-test
input-test: ## Negative tests of the input checks on real RPMs (tampered, missing, extra)
	scripts/test-inputs

.PHONY: sbom
sbom: ## SPDX SBOMs of both images and a report-only vulnerability scan (P1-16)
	scripts/sbom

.PHONY: repro
repro: ## Two independent clean builds and the R-01/R-02/R-03 comparison (CI runner)
	scripts/repro-build

.PHONY: image
image: ## Build the sealed aegis-base and aegis-dev container images (B-01); needs 'builder'
	scripts/build-image

.PHONY: disk
disk: ## Install both variants into image files under out/ (never a real disk)
	scripts/build-disk localhost/aegis-dev:latest out/disk.raw
	scripts/build-disk localhost/aegis-base:latest out/disk-base.raw

.PHONY: image-gui
image-gui: ## M4-GUI: build and seal the base, development and graphical images
	AEGIS_WITH_GUI=1 scripts/build-image

.PHONY: disk-gui
disk-gui: ## M4-GUI: install the graphical image into out/disk-gui.raw
	AEGIS_DISK_SIZE=20G scripts/build-disk localhost/aegis-gui:latest out/disk-gui.raw

.PHONY: export-gui
export-gui: ## GUI v1: export out/disk-gui.raw as a compressed QCOW2 with launcher and guide
	scripts/export-qcow2 --gui

.PHONY: gui-local-test
gui-local-test: ## GUI v1: boot the exported GUI QCOW2 with the published Linux launcher
	scripts/run-gui-local-test

.PHONY: rootfs-gui
rootfs-gui: ## Live ISO: build the unsealed graphical root filesystem only (no sealing)
	AEGIS_WITH_GUI=1 AEGIS_ROOTFS_ONLY=1 AEGIS_SKIP_UPDATE_IMAGE=1 scripts/build-image

.PHONY: live-iso
live-iso: ## Live ISO: build out/release-live/AEGIS-OS-GUI-v2-Live.iso (needs rootfs-gui)
	scripts/build-live-iso

.PHONY: live-test
live-test: ## Live ISO: check the ISO and boot it on VirtualBox-like hardware in QEMU
	scripts/run-live-tests

.PHONY: gui-test
gui-test: ## M4-GUI: boot the graphical image under Secure Boot and run the GUI tests
	scripts/run-gui-tests

.PHONY: builder
builder: ## Build the test and tools container (QEMU, firmware, pytest, signing tools)
	scripts/build-builder

.PHONY: inventory
inventory: ## Record packages, units, privileged files and permissive domains of both images
	scripts/inventory-image

.PHONY: export
export: ## Export out/disk.raw as a compressed QCOW2 with checksum, launchers and guide
	scripts/export-qcow2

.PHONY: image-test
image-test: ## Golden manifests (B-02, B-03, B-04), sealed image (B-06), SBOM (B-07)
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
all: inputs builder image sbom inventory image-test disk export vm-test ## Build, inventory, install, export, boot and test everything

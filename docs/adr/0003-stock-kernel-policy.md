# ADR-0003: Stock Fedora kernel, no patches

Status: Accepted
Date: 2026-11-13

## Context

Custom kernels add maintenance burden and delay security fixes.

## Decision

Ship the unmodified Fedora kernel. Hardening uses kernel arguments and sysctl only. No out-of-tree modules in Phase 1. Any kernel change needs before/after measurements (Phase 5).

## Consequences

- Phase 3 NVIDIA support must sign prebuilt modules at image build time.
- Arguments with a known cost (`init_on_free=1`, `nosmt`, `debugfs=off`, mitigation changes) are excluded until measured.

## Verification

V-03 (kernel version, taint 0), V-19 (arguments and sysctl equal golden list).

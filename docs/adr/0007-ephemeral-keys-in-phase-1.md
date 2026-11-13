# ADR-0007: Ephemeral signing keys in Phase 1

Status: Accepted
Date: 2026-11-13

## Context

A real key hierarchy needs an offline root and a ceremony. Storing long-lived keys as CI secrets before that exists creates risk for no benefit.

## Decision

Secure Boot and cosign keys are generated per CI run, or per developer under the git-ignored `.secrets/`, used and discarded. The repository stores no signing secrets in Phase 1.

## Consequences

- Published Phase 1 images are not a usable update trust root.
- Phase 2 defines the persistent hierarchy (offline root, hardware-backed signing).

## Verification

S-02, B-05, static test that `.secrets/` is ignored.

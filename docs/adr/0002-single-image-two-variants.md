# ADR-0002: One image, two variants

Status: Accepted
Date: 2026-11-13

## Context

Tests need a way into the running system, but a release image must not carry remote access.

## Decision

`aegis-base` is release-shaped (no SSH, root locked, no users). `aegis-dev` is `FROM aegis-base` and adds SSH with key-only login and test-only policy. Login keys are injected when the VM starts, never baked in.

## Consequences

- VM tests run against `aegis-dev`; `aegis-base` is checked at image level and by serial-console boot.
- Anything added to `aegis-dev` must be impossible to mistake for a release feature.

## Verification

B-02 to B-04 golden manifests exist for both variants; V-17.

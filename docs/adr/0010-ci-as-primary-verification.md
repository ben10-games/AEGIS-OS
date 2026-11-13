# ADR-0010: GitHub Actions as the primary verification environment

Status: Accepted
Date: 2026-11-13

## Context

Claude Cloud sessions have no KVM, no container daemon and no access to Fedora registries (probed 2026-11-13).

## Decision

Image builds, disk builds and VM tests run in GitHub Actions on hosted Linux runners, and identically on a local KVM machine through the same Make targets. Cloud sessions author changes and run the static tier only.

## Consequences

- Feedback requires a push; commits stay small.
- If hosted runners lack usable KVM (assumption A1), VM tests move to a local or self-hosted runner.

## Verification

Task P1-00 probe output recorded in `PROJECT_STATE.md`.

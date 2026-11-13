# ADR-0006: Build in a pinned container; pin every input

Status: Accepted
Date: 2026-11-13

## Context

Builds must give the same result in CI and on a developer machine, and must not silently pick up new upstream content.

## Decision

All image work runs inside a builder container pinned by digest. The base image is pinned by digest and mirrored. RPMs come from a generated lockfile with checksums. CI actions are pinned by commit SHA; Python lint tools are installed with `--require-hashes`. The task runner is GNU Make.

## Consequences

- Deviation from the approved blueprint: the blueprint named `just`. Make is already present in Claude Cloud, on CI runners and in Fedora, so it removes one tool that would itself need pinning.
- Input updates arrive only as reviewed commits produced by a scheduled bump job.

## Verification

S-03, R-01, R-02.

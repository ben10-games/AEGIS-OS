# ADR-0013: Custom minimal base versus stock fedora-bootc

Status: Open
Date: 2026-11-13

## Context

The stock `fedora-bootc` image contains packages AEGIS may not need. Fedora supports generating a custom minimal base.

## Decision

Not decided. Phase 1 derives from the stock image; the golden package manifest (B-02) gives the data for a Phase 2 decision.

## Consequences

- A custom base reduces attack surface but adds a build stage to maintain.

## Verification

Phase 2.

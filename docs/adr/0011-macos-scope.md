# ADR-0011: macOS application support is out of scope

Status: Accepted
Date: 2026-11-13

## Context

Running macOS in a virtual machine on non-Apple hardware breaches Apple's licence. Darling, the only translation layer, is experimental and mostly command-line.

## Decision

AEGIS ships no macOS virtual-machine support. Darling may be evaluated in Phase 3 as an untrusted-tier experiment with no compatibility promise.

## Consequences

- The project brief's macOS goal is reduced to an evaluation.

## Verification

None in Phase 1.

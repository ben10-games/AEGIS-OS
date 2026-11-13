# ADR-0009: Four software trust tiers

Status: Accepted
Date: 2026-11-13

## Context

Wine and Proton run Windows malware as readily as Windows software. Compatibility is not isolation.

## Decision

Tier 0: the sealed OS image. Tier 1: vetted native applications in Flatpak sandboxes. Tier 2: approved compatibility applications (Steam, Proton, Wine) inside a sandbox with no access to the home directory or credentials. Tier 3: anything untrusted runs in a disposable KVM virtual machine with no host data.

## Consequences

- Implementation is Phase 3; Phase 1 only fixes the model so the foundation does not preclude it.
- Tier 3 Windows guests will not have native GPU performance.

## Verification

Phase 3 acceptance tests.

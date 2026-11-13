# ADR-0001: Fedora bootc as the foundation

Status: Accepted
Date: 2026-11-13

## Context

AEGIS needs mandatory access control, a verified root filesystem, image-based updates with rollback, and a current graphics stack, without becoming its own distribution.

## Decision

Derive AEGIS OS from `quay.io/fedora/fedora-bootc` (Fedora 45), pinned by digest. No second base distribution.

## Consequences

- SELinux policy, kernel and security updates come from Fedora.
- Fedora's roughly 13-month release life forces regular rebases; input bumps are automated and gated by the full test suite.
- Alternatives rejected: Universal Blue (third-party build chain in the trusted base), openSUSE Aeon (no verified image), NixOS (no supported SELinux), Ubuntu Core (AppArmor, snap-centred), Arch A/B (no MAC), mkosi + sysupdate (become the distribution).

## Verification

B-01 builds from the pinned base; `image/base.lock` holds the digest.

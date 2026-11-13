# ADR-0004: Sealed images on the bootc composefs backend

Status: Provisional
Date: 2026-11-13

## Context

bootc has two storage backends with no supported in-place migration. Only the composefs backend supports sealed images (signed UKI carrying the root filesystem digest, fs-verity enforced) and systemd-boot. Upstream bootc 1.17 documents both under its stability guarantees; Fedora's own sealed desktop images were test-only in spring 2026.

## Decision

Target the composefs backend with systemd-boot and a signed UKI. The decision becomes Accepted only when gate G1 passes on the pinned base: install, Secure Boot, upgrade, rollback and tamper rejection in a VM. If G1 fails, fall back to the ostree backend with shim and GRUB and mark this ADR "fallback active".

## Consequences

- `bootupd` must be absent from the image, otherwise GRUB is selected.
- No automatic rollback on failed boot yet on this backend; Phase 2 item.
- The backend difference is confined to one Containerfile stage and the disk-build flags.

## Verification

B-06, V-04, V-05, V-06, V-07, V-13, V-14 (task P1-11, P1-12, P1-14).

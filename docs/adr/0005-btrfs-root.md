# ADR-0005: btrfs root filesystem

Status: Accepted
Date: 2026-11-13

## Context

The composefs backend needs fs-verity, which ext4 and btrfs provide and XFS does not.

## Decision

Root filesystem is btrfs (zstd:1, noatime) on a GPT disk with a 2 GiB ESP and no separate `/boot`. ext4 is the fallback if btrfs misbehaves with the composefs backend.

## Consequences

- Snapshots and reflinks are available later for user-data recovery and disposable VM disks.
- The 2 GiB ESP holds UKIs for booted, staged and rollback deployments; machines sharing a small ESP will use XBOOTLDR (Phase 6).

## Verification

B-08 (partition table and filesystem type), V-06.

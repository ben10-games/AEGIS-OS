# ADR-0012: Secure Boot key enrollment on physical hardware

Status: Open
Date: 2026-11-13

## Context

Phase 1 enrolls throw-away keys into virtual firmware. Real machines need either AEGIS keys enrolled in firmware (keeping Microsoft's certificate for option ROMs) or a Microsoft-signed shim with an enrolled machine-owner key.

## Decision

Not decided. To be settled in Phase 2 (key hierarchy) and Phase 6 (hardware).

## Consequences

- Until decided, no claim is made about Secure Boot on physical hardware.

## Verification

Phase 6.

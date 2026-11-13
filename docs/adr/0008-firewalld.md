# ADR-0008: firewalld as the firewall manager

Status: Accepted
Date: 2026-11-13

## Context

A static nftables ruleset is smaller, but Phase 3 needs per-network zones and integration with podman and libvirt.

## Decision

Use firewalld with the nftables backend. Ship an AEGIS default zone that drops unsolicited inbound traffic, defined under `/usr/lib/firewalld`.

## Consequences

- A Python daemon stays resident; its memory cost is recorded in the Phase 1 baseline and revisited in Phase 5 with data.

## Verification

V-10, V-11.

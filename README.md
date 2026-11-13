# AEGIS OS

AEGIS OS is a security-focused desktop operating system built as a derived
[Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/) image. The target boot chain is
UEFI Secure Boot → signed systemd-boot → signed Unified Kernel Image → composefs root
filesystem verified with fs-verity → SELinux-enforcing userspace.

**Project status: Phase 1 (Core Foundation), early.** Nothing here is installable yet.
`PROJECT_STATE.md` is the single source of truth for what exists and what has been verified.

## Important limitations

- No image published from this repository is suitable for real use. Phase 1 signs with
  throw-away keys that exist only for the duration of one build.
- Phase 1 disk images are unencrypted development artifacts for virtual machines.
- AEGIS OS does not and will not claim immunity from malware or compromise.

## Where to start

| You want to | Read |
|---|---|
| Understand the design | `docs/architecture/phase-1-blueprint.md` |
| See why a decision was made | `docs/adr/` |
| Know the current state and next task | `PROJECT_STATE.md` |
| Continue development with an AI assistant | `CLAUDE.md` |

## Checks you can run anywhere

```bash
make static
```

This runs the repository rule tests and Python linting. It needs only `python3`, `pytest`
and `ruff`. Image builds and virtual-machine tests run in GitHub Actions or on a Linux
machine with KVM; they do not run in restricted cloud sandboxes.

## Licence

Not yet chosen. Until a licence file is added, no rights are granted.

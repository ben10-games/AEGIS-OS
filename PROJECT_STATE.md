# AEGIS OS — project state

This file is the single source of truth for what exists and what has been verified.
It is updated in the same commit as the work it describes. A test is listed as verified
only if it actually ran and passed, with the commit and where it ran.

## 1. Resume here

- **Branch:** `claude/aegis-os-architecture-ayxptj`
- **Phase / milestone:** Phase 1, milestone M0 (repository and tooling)
- **Blocked:** the first push was refused on 2026-11-13 (HTTP 403: the Claude GitHub App has
  no access to this repository). Nothing is on GitHub yet. Push the branch first.
- **Next task:** after the push, read the result of the `probe` and `lint` workflows,
  record them in sections 5, 8 and 10 below, then start **P1-03 (builder container)**.
- **Last green CI run:** none yet
- **To continue:**
  1. `make static` (must pass before every commit).
  2. Check GitHub Actions for the latest commit on the branch (`lint`, `probe`).
  3. Follow the task order in `docs/architecture/phase-1-blueprint.md` section 8.

## 2. Status

| Task | Title | State | Commit / evidence |
|---|---|---|---|
| P1-00 | Environment probe | in progress | script and workflow written; CI result not yet read |
| P1-01 | Repository scaffold | done | initial commit series |
| P1-02 | Static tooling and lint workflow | in progress | `make static` passes in cloud; full `make lint` not yet seen green in CI |
| P1-03 | Builder container | todo | |
| P1-04 | Minimal derived image | todo | |
| P1-05 | Disk image | todo | |
| P1-06 | VM harness and first boot | todo | |
| P1-07 | Variant split and golden manifests | todo | |
| P1-08 | Operating system baseline | todo | |
| P1-09 | SELinux enforcement validation | todo | |
| P1-10 | Ephemeral key tooling | todo | |
| P1-11 | Sealed image, gate G1 | todo | |
| P1-12 | Tamper and negative boot tests | todo | |
| P1-13 | Signing and signature policy | todo | |
| P1-14 | Update and rollback tests | todo | |
| P1-15 | Input pinning | todo | |
| P1-16 | Reproducibility, SBOM, vulnerability report | todo | |
| P1-17 | Metrics baseline | todo | |
| P1-18 | Operations and development documentation | todo | |
| P1-19 | Phase 1 exit review | todo | |

## 3. Architecture decisions

See `docs/adr/README.md` for the index. ADR-0004 (sealed composefs backend) is
**Provisional** until gate G1 passes. ADR-0012 and ADR-0013 are **Open**.

Deviations from the approved blueprint:

| Deviation | Reason | Recorded in |
|---|---|---|
| GNU Make instead of `just` as the task runner | Make is preinstalled everywhere the project runs; installing extra tools in Claude Cloud was refused | ADR-0006 |
| hadolint not in the static tier yet | No pinned source for it that works in both cloud and CI; to be added with the builder container (P1-03) | this file |
| `probe` workflow also runs on pushes that change it, not only manually | Lets a cloud session obtain the result without a manual trigger | this file |

## 4. Completed milestones

None.

## 5. Verified tests

| Test | Result | Commit | Where it ran |
|---|---|---|---|
| Static repository rules (`make static`: part of S-01, S-03, S-04) | pass | initial commit series | Claude Cloud |

No image (B), virtual-machine (V) or reproducibility (R) test has run yet.
S-01 (all linters) and S-02 (gitleaks) have not yet been seen passing in CI.

## 6. Known bugs

None recorded.

## 7. Security limitations

- No operating-system image exists yet; no security property has been demonstrated.
- Planned Phase 1 limitations (see blueprint section 11): no disk encryption, throw-away
  signing keys, no automatic rollback on failed boot, no application sandboxing, `/etc`
  and `/var` are not integrity-protected, root can still change SELinux mode at runtime.

## 8. Assumptions

| ID | Assumption | State |
|---|---|---|
| A1 | GitHub-hosted Linux runners expose usable KVM | open (tested by `probe` workflow) |
| A2 | `fedora-bootc:45` ships bootc 1.16 or newer | open (tested by `probe` workflow) |
| A3 | `bootc install to-disk` supports btrfs with the composefs backend | open (P1-05, P1-11) |
| A4 | Fedora's updates-archive repository is usable for locked RPMs | open (P1-15) |
| A5 | Container signature policy is enforced on the composefs backend | open (P1-14, test V-15) |
| A6 | SSH key injection through a systemd credential on the QEMU command line works | open (P1-06) |

## 9. Outstanding tasks and open decisions for the owner

Open decisions (none block current work):

- Repository licence.
- Whether the repository is public (affects CI minutes and package visibility).
- Whether a local Linux machine with KVM is available for interactive debugging.
- Whether to allow Fedora hosts in the Claude Cloud network policy later.

## 10. Environment notes

Claude Cloud, probed 2026-11-13:

- No `/dev/kvm`, no vmx/svm CPU flags.
- Docker client present, no daemon running; no podman, buildah, skopeo, QEMU.
- `quay.io`, `registry.fedoraproject.org` and Fedora mirrors are blocked by network policy.
- `ghcr.io`, `github.com`, `pypi.org`, `registry-1.docker.io` are reachable.
- Installing additional tools (pip, go install) was refused by the session's permission
  policy, so only `python3`, `pytest`, `ruff`, `make` and `git` are available. shellcheck,
  yamllint, actionlint and gitleaks therefore run only in CI.

GitHub Actions runners: not yet probed.

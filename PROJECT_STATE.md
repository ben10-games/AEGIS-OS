# AEGIS OS — project state

This file is the single source of truth for what exists and what has been verified.
It is updated in the same commit as the work it describes. A test is listed as verified
only if it actually ran and passed, with the commit and where it ran.

## 1. Resume here

- **Branch:** `claude/aegis-os-architecture-ayxptj`
- **Phase / milestone:** Phase 1, milestone M1 (first boot). M0 is complete.
- **Next task:** get the `build` workflow green (P1-03 to P1-06: images, disk, first boot
  and shutdown in a VM), then record V-01 and V-02 in section 5.
- **Last green CI run:** `lint` on `384c2e3`,
  https://github.com/ben10-games/AEGIS-OS/actions/runs/43458827403
- **To continue:**
  1. `make static` (must pass before every commit).
  2. Check GitHub Actions for the latest commit on the branch (`lint`, `probe`).
  3. Follow the task order in `docs/architecture/phase-1-blueprint.md` section 8.

## 2. Status

| Task | Title | State | Commit / evidence |
|---|---|---|---|
| P1-00 | Environment probe | done | `6ccd8fb`; `probe` run 43459049502 green |
| P1-01 | Repository scaffold | done | `d373736` |
| P1-02 | Static tooling and lint workflow | done | `e5c0f94`; `lint` run 43458827403 green |
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

| Milestone | Date | Evidence |
|---|---|---|
| M0 Repository and tooling (P1-00 to P1-02) | 2026-11-13 | `lint` run 43458827403, `probe` run 43459049502 |

## 5. Verified tests

| Test | Result | Commit | Where it ran |
|---|---|---|---|
| S-01 Linters (pytest rules, ruff, shellcheck, yamllint, actionlint) | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-02 Secret scan (gitleaks, full history) | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-03 Actions pinned by commit SHA | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-04 State file and ADR index | pass | `384c2e3` | GitHub Actions run 43458827403 |

No image (B), virtual-machine (V) or reproducibility (R) test has run yet.

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
| A1 | GitHub-hosted Linux runners expose usable KVM | **confirmed** (QEMU started with `-accel kvm`, probe run 43459049502) |
| A2 | `fedora-bootc:45` ships bootc 1.16 or newer | **confirmed** (bootc 1.17.1, probe run 43459049502) |
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

GitHub Actions hosted runner (`ubuntu-24.04`), probed 2026-11-13, run 43459049502:

- 4 CPUs, 15.6 GiB RAM, 83 GiB free disk, kernel 7.0.0-azure.
- `/dev/kvm` present; usable by the runner user after a udev rule; QEMU 8.2.2 (apt) starts
  with KVM acceleration.
- Loop devices can be attached inside a privileged podman container.
- podman 4.9.3, buildah 1.33.7, skopeo 1.13.3, Docker 28.0.4 (daemon running).
- quay.io, registry.fedoraproject.org, Fedora mirrors, ghcr.io all reachable.

`quay.io/fedora/fedora-bootc:45` on 2026-11-13
(`sha256:42259b1db41a7f792a19cfd28e0c66e3e415392109a7d7095f292ad1e2a56453`):

- bootc 1.17.1, kernel 7.3.3-300.fc45, systemd 262.1, selinux-policy-targeted 45.24,
  openssh-server 10.5p1, 540 packages.
- `bootupd` 0.3.2 is installed (must be removed for the sealed path, P1-11).
- Not installed: `systemd-boot-unsigned`, `systemd-ukify`, `firewalld`, `audit`.

GitHub quirk: a workflow with a `paths` filter did not start on the first push of a new
branch; it started on the next push that touched a matching path.

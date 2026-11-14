# AEGIS OS — project state

This file is the single source of truth for what exists and what has been verified.
It is updated in the same commit as the work it describes. A test is listed as verified
only if it actually ran and passed, with the commit and where it ran.

## 1. Resume here

- **Branch:** `claude/aegis-os-architecture-ayxptj`
- **Phase / milestone:** Phase 1, milestone M2 (baseline configuration) in progress.
  M0 and M1 are complete. The approved M2 plan has eight increments; see section 2.
- **Next task:** finish increment 4 of M2 (firewall and audit), then kernel arguments
  and sysctl, networking, SELinux verification and the BUG-1 fix, and the before/after
  record. Do not start M3 before M2 is complete.
- **Reading results from a cloud session:** artifacts cannot be downloaded there (the
  storage host is blocked). Read the end of the `build` job log: the "Collect results"
  step prints `scripts/summarize-results`, with short inventories, the differences
  between golden manifests and the build, measurements and test reports last.
- **To continue:**
  1. `make static` (must pass before every commit).
  2. Push, then read the `lint` and `build` results for that commit.
  3. When an image change alters a golden manifest, copy the new entries from the
     "differences between the golden manifests and this build" block of the job log
     into `tests/golden/` in the same commit series.

## 2. Status

| Task | Title | State | Commit / evidence |
|---|---|---|---|
| P1-00 | Environment probe | done | `6ccd8fb`; `probe` run 43459049502 green |
| P1-01 | Repository scaffold | done | `d373736` |
| P1-02 | Static tooling and lint workflow | done | `e5c0f94`; `lint` run 43458827403 green |
| P1-03 | Builder container | done | `fc13ac6`; `build` run 43460695621 |
| P1-04 | Minimal derived image | done | `fc13ac6`; `build` run 43460695621 |
| P1-05 | Disk image | done | `9c8807c`; `build` run 43460695621 |
| P1-06 | VM harness and first boot | done | `399d421`; `build` run 43460695621 |
| P1-07 | Variant split and golden manifests | done | `5d839d4`; `build` run 43547501384 |
| P1-08 | Operating system baseline | in progress | identity and service baseline done (`bf592c8`, run 43550888887); firewall and audit pushed; kernel arguments, sysctl, networking to follow |
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
| The builder container holds test tooling only (QEMU, firmware, swtpm, pytest). Image builds and the disk install use the host's podman directly | A privileged loopback install nested inside another container is fragile; one level of nesting worked first time | this file |
| The builder container is built from the pinned `fedora-bootc` base, not a plain Fedora image | One pinned input instead of two; layers are shared with the OS image build | `build/builder/Containerfile` |
| One `build` workflow does images, disk and VM tests; there is no separate `vm-test` workflow yet | Multi-gigabyte images are not passed between jobs; split when a registry exists (P1-13) | this file |
| No `build/disk/phase1.toml`; the ESP has bootc's default size, not 2 GiB | `bootc install to-disk` creates the layout itself; the 2 GiB ESP matters only for UKIs and is handled in P1-11 | this file |
| Disk image is raw (`out/disk.raw`) with a qcow2 overlay at test time, not a stored qcow2 | Nothing consumes a standalone qcow2 yet | this file |

## 4. Completed milestones

| Milestone | Date | Evidence |
|---|---|---|
| M0 Repository and tooling (P1-00 to P1-02) | 2026-11-13 | `lint` run 43458827403, `probe` run 43459049502 |
| M1 First verified boot (P1-03 to P1-06) | 2026-11-13 | `build` run 43460695621 on `399d421`: 8 VM tests passed in 43.5 s under KVM; repeated on `a3a5004` (run 43461672095) |

Milestone tags `p1-m0` (`cdce239`) and `p1-m1-first-boot` (`399d421`) exist only in the
session that created them: pushing tags was refused (HTTP 403; the session may push the
development branch only). The owner can create them from the commit hashes above.

## 5. Verified tests

| Test | Result | Commit | Where it ran |
|---|---|---|---|
| S-01 Linters (pytest rules, ruff, shellcheck, yamllint, actionlint) | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-02 Secret scan (gitleaks, full history) | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-03 Actions pinned by commit SHA | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-04 State file and ADR index | pass | `384c2e3` | GitHub Actions run 43458827403 |

| B-01 Image construction (build exits 0, `bootc container lint --fatal-warnings`, label `containers.bootc=1`), both variants | pass | `399d421` | GitHub Actions run 43460695621 |
| B-08 Disk image (GPT, EFI system partition, btrfs root), checked from inside the VM; raw image, not qcow2 | pass | `399d421` | GitHub Actions run 43460695621 |
| V-01 Boot: SSH reachable, system state `running`, no failed units | pass | `399d421` | GitHub Actions run 43460695621, KVM |
| V-02 Shutdown: QEMU exit 0 after `poweroff`, kernel "Power down" on serial, clean second boot, `/etc` and `/var` sentinels kept | pass | `399d421` | GitHub Actions run 43460695621, KVM |

Early signals that also passed in run 43460695621 (they do **not** replace the full
tests): the booted system is the image built from the tested commit; SELinux reports
Enforcing (part of V-08); `/usr` is read-only (part of V-06).

Measurements from run 43461672095 (`a3a5004`; 2 vCPU, 4 GiB, KVM on a hosted runner).
These are observations, not the V-12 baseline, which is task P1-17:

| Metric | First boot | Second boot |
|---|---|---|
| Startup (kernel + initrd + userspace) | 11.7 s (1.1 + 3.8 + 6.8) | 7.9 s (1.1 + 2.8 + 4.0) |
| Memory in use (`free -m`, "used") | 462 MiB | 436 MiB |
| Failed units | 0 | 0 |
| SELinux denials logged | 3 | 3 |

Memory in use is above the blueprint's provisional 400 MiB budget for V-12; the image is
still the unmodified Fedora service set, so this is expected to change in P1-08.

| B-02 Package manifest (names, 540 packages), both variants | pass | `5d839d4` | GitHub Actions run 43547501384 |
| B-03 Enabled and masked units, both variants | pass | `5d839d4` | GitHub Actions run 43547501384 |
| B-04 Setuid/setgid files and file capabilities, both variants | pass | `5d839d4` | GitHub Actions run 43547501384 |
| Golden manifests detect unlisted content (negative check) | pass | `58a46d0` | run 43546633024 failed for exactly the four manifests that were still empty |
| Release variant boots to a console login prompt with no failed unit and powers off on the ACPI power button (V-01/V-02 for `aegis-base`, console only) | pass | `5d839d4` | GitHub Actions run 43547501384, KVM |

| V-17 Accounts: root locked, no account with a usable or empty password, no regular users; dev SSH server offers public-key login only | pass | `bf592c8` | GitHub Actions run 43550888887, KVM |
| V-20 Automatic update timer is masked and not scheduled | pass | `bf592c8` | GitHub Actions run 43550888887, KVM |
| Service baseline: every unit the preset turns off is inactive and disabled at runtime | pass | `bf592c8` | GitHub Actions run 43550888887, KVM |
| Identity: `os-release` and hostname say AEGIS in both variants; release variant answers nothing on the SSH port | pass | `bf592c8` | GitHub Actions run 43550888887, KVM |
| `/etc` changes equal the reviewed list (ADR-0014), both variants | pass | `bf592c8` | GitHub Actions run 43550888887 |

Not yet run: B-05 to B-07, V-03 to V-16 and V-18 to V-19 (except the parts noted above), all R tests.

### "Before" measurements for M2

Stock Fedora service set, `aegis-dev`, first boot, run 43546633024 (`58a46d0`; 2 vCPU,
4 GiB, KVM). These are the numbers the M2 baseline is compared with.

| Metric | Value |
|---|---|
| Startup, first boot | 8.9 s (0.9 kernel + 2.6 initrd + 5.4 userspace) |
| Startup, second boot | 7.1 s |
| Memory in use (MemTotal - MemAvailable) | 472 MiB |
| Running services | 22 |
| Enabled units | 63 |
| Active timers | 6 |
| TCP/UDP listeners | 14 (sshd on all interfaces, LLMNR 5355 and mDNS 5353 on all interfaces, DNS stub and chrony on loopback) |
| Processes | 153 |
| Failed units | 0 |
| SELinux denials per boot | 3 (BUG-1) |
| SELinux permissive domains in the policy | 31 |
| Setuid/setgid files, files with capabilities | 17, 8 |
Nothing has been verified on a local workstation or on physical hardware.

## 6. Known bugs

| ID | Description | Impact | Plan |
|---|---|---|---|
| BUG-1 | Every boot logs 3 SELinux denials: `bootloader-update.service` runs `bootupctl` (domain `bootupd_t`, declared permissive by Fedora), which reads `/sysroot/.bootc-aleph.json`. Root cause, confirmed in run 43545946188: three things created in the physical root at install time (`/sysroot/.bootc-aleph.json`, `/sysroot/boot/grub2`, `/sysroot/boot/bootupd-state.json`) are labelled `default_t`. Fedora's policy has no file-context rule for those `/sysroot/...` paths, and `bootupd_t` may read `root_t` and `boot_t` but not `default_t`. No file anywhere is `unlabeled_t`, so this is not a labelling failure of the build host. Only the first denied access per type is logged in a permissive domain, so the other two files are affected as well. | Nothing is blocked (the domain is permissive), but V-08 requires zero denials. | M2 increment 7: file-context rules in an AEGIS policy module giving these paths the types `bootupd_t` is already allowed to use. No allow rule, no `dontaudit`. Upstream report to be drafted. |
| BUG-2 | The image still identifies itself as Fedora (`os-release`, hostname `fedora`). | Cosmetic. | M2 increment 3. |
| BUG-3 | At power-off the console shows "Failed to unmount /run/shutdown/mounts/...: Device or resource busy" and "Not all file systems unmounted, 1 left" before "Syncing filesystems" and "Power down". Seen on `aegis-base` in run 43546633024. | None observed: the following boot shows no filesystem recovery (V-02). Looks like the physical root that backs the running deployment. | Confirm the cause; re-check after the sealed boot chain changes the mount layout (P1-11). |
| BUG-4 | Closed. `podman build` 4.9 left an empty `/etc/hostname` in the image; the image now ships that file with the static hostname `aegis`. | | |
| BUG-5 | The initramfs is the one built by Fedora. It contains Fedora's `os-release`, so early boot identifies itself as Fedora and sets the hostname `fedora` until the real system applies `/etc/hostname`. | Cosmetic in M2. | The initramfs is regenerated when the UKI is built for the sealed boot chain (P1-11). |

## 7. Security limitations

- The M1 image is the stock Fedora bootc base plus identity metadata. It boots with the
  ostree backend and GRUB, **without** Secure Boot, without a sealed root, unsigned, and
  with no AEGIS hardening. The only demonstrated properties are: it boots, SELinux is
  enforcing, and `/usr` is read-only.
- `aegis-base` still has whatever services the Fedora base enables (including possibly
  sshd); the release-shaped service set is P1-07/P1-08.
- SELinux denials occur during boot (BUG-1); V-08 is not met.
- The disk has a BIOS boot partition and a 512 MiB ESP because `bootc install to-disk`
  was run with `--generic-image`; BIOS boot support is not wanted in the final design.
- Planned Phase 1 limitations (see blueprint section 11): no disk encryption, throw-away
  signing keys, no automatic rollback on failed boot, no application sandboxing, `/etc`
  and `/var` are not integrity-protected, root can still change SELinux mode at runtime.

## 8. Assumptions

| ID | Assumption | State |
|---|---|---|
| A1 | GitHub-hosted Linux runners expose usable KVM | **confirmed** (QEMU started with `-accel kvm`, probe run 43459049502) |
| A2 | `fedora-bootc:45` ships bootc 1.16 or newer | **confirmed** (bootc 1.17.1, probe run 43459049502) |
| A3 | `bootc install to-disk` supports btrfs with the composefs backend | partly confirmed: btrfs works with the ostree backend (run 43460695621); composefs backend still open (P1-11) |
| A4 | Fedora's updates-archive repository is usable for locked RPMs | open (P1-15) |
| A5 | Container signature policy is enforced on the composefs backend | open (P1-14, test V-15) |
| A6 | SSH key injection through a systemd credential on the QEMU command line works | **confirmed** (run 43460695621) |

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

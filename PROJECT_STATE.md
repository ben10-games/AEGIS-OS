# AEGIS OS — project state

This file is the single source of truth for what exists and what has been verified.
It is updated in the same commit as the work it describes. A test is listed as verified
only if it actually ran and passed, with the commit and where it ran.

## 1. Resume here

- **Branch:** `claude/aegis-os-architecture-ayxptj`
- **Phase / milestone:** Phase 1. M0, M1 and **M2 (baseline configuration) are
  complete**; see sections 4 and 5 and `docs/architecture/security-baseline.md`.
- **Next task:** the owner's request for a downloadable development image for local
  virtual-machine testing (see "Local VM image" below). M3 (sealed boot chain, P1-10 to
  P1-12) has **not** been started and waits for the owner's go-ahead.
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

### Local VM image (owner request, in progress)

Committed, **not yet verified in CI**: `LOCAL_VM_GUIDE.md`, `local-vm/run-aegis-vm.sh`,
`local-vm/run-aegis-vm.ps1`, `scripts/export-qcow2` (`make export`),
`tests/vm/test_local_image.py`, `tests/static/test_local_launcher.py`, and in the `build`
workflow the export step, the publication step (artifact `aegis-os-dev-qcow2`, only on a
manual run or when the head commit message contains `[publish-image]`, only after every
test passed) and the job `windows-launch`.

Run 43718015605 (`0b3da6c`, renewed base): 60 of 61 tests passed, among them the 55 M2
tests and, for the exported image, SSH login with a launch-time key, system health,
SELinux enforcing, power-off and unchanged checksum. The automatic console login
failed, so nothing was published.

Next: confirm the drop-in based console login in CI, then record here what was verified
and bring `LOCAL_VM_GUIDE.md` section 9 in line with it.

New external host, to be confirmed by the owner: the `windows-launch` job installs QEMU
on the hosted Windows runner with `choco install qemu` (Chocolatey community
repository). It is a test-only job; nothing from it enters the image.

**Design decisions for the local-VM image (so they need not be re-derived)**

- The image is `aegis-dev` exported as compressed QCOW2 (zlib, for compatibility).
- No password or key in the image. Login is granted at launch through systemd
  credentials in SMBIOS strings: `ssh.authorized_keys.root` for SSH (proven), and for
  the serial console `systemd.unit-dropin.serial-getty@ttyS0.service`, a drop-in that
  starts `agetty --autologin root`.
- The credentials `agetty.autologin=root` and `login.noauth=yes` do **not** work on this
  image: run 43718015605 showed a plain login prompt. Cause not established; a likely
  one is that agetty ignores `$CREDENTIALS_DIRECTORY` after an SELinux domain
  transition (secure-execution mode).
- CI must boot the exported file with `local-vm/run-aegis-vm.sh` (the published
  launcher), using `--snapshot`, before the artifact is uploaded.
- The Windows launcher defaults to software emulation; WHPX is documented as untested.

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
| P1-08 | Operating system baseline | done | `e378b1e`; `build` run 43554108533 (identity, services, firewall, audit, kernel arguments, sysctl, networking) |
| P1-09 | SELinux enforcement validation | done | `c3308a8`; `build` run 43557838924 (V-08: zero denials, labels, enforcement self-test) |
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
| M2 Baseline configuration (P1-07 to P1-09) | 2026-11-14 | `build` run 43557838924 on `c3308a8`: 14 image tests and 55 VM tests passed (both variants, KVM); `lint` run 43557838949 green on the same commit. Same result on `3514aec` (run 43557821995) |

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

| V-03 Kernel: one kernel in the image and it is the one running; not tainted; only allow-listed error messages | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-10 Networking: address and route from DHCP; name resolution through systemd-resolved; outbound fetch by name; listeners equal the golden list (harness DNS and HTTP servers, no internet; HTTP not HTTPS) | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-11 Firewall: firewalld active, default zone `aegis` with target DROP, drop verdict in the kernel ruleset; a listener outside the zone is unreachable from outside, with positive controls | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-19 Kernel arguments, lockdown in integrity mode, 31 sysctl values equal the golden lists; reverse-path filtering never off | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| Audit daemon attached to the kernel, auditing enabled, log written | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |

| V-08 SELinux: enforcing and not switchable off from the kernel command line; zero denials during boot (audit log and journal); install-time files carry the types `bootupd` may use; no `unlabeled_t` or `default_t` file; no service in `unconfined_service_t` or `initrc_t`; self-test domain may read what its policy allows and is refused what it does not, logged with `permissive=0` | pass | `c3308a8` | GitHub Actions run 43557838924, KVM (also run 43557821995) |
| Whole M2 suite on one commit: 14 image tests, 55 VM tests (includes the M1 tests B-01, B-08, V-01, V-02) | pass | `c3308a8` | GitHub Actions run 43557838924, KVM (also run 43557821995) |

Not yet run: B-05 to B-07, V-04 to V-07, V-09, V-12 to V-16, V-18 (except the parts noted above), all R tests.

### Measurements before and after M2

`aegis-dev`, first boot unless stated, 2 vCPU, 4 GiB, KVM on a hosted runner. Before:
stock Fedora service set, run 43546633024 (`58a46d0`). After: M2 baseline, run
43557838924 (`c3308a8`); run 43557821995 gave 9.3 s, 7.4 s and 529 MiB. Single runs on shared runners; differences of a few tenths of
a second or a few MiB are noise. These are observations, not the V-12 baseline (P1-17).

| Metric | Before | After |
|---|---|---|
| Startup, first boot | 8.9 s (0.9 kernel + 2.6 initrd + 5.4 userspace) | 9.3 s (0.9 + 2.6 + 5.8) |
| Startup, second boot | 7.1 s | 7.1 s |
| Memory in use (MemTotal - MemAvailable) | 472 MiB | 509 MiB |
| Running services | 22 | 22 |
| Enabled units | 63 | 58 |
| Active timers | 6 | 4 |
| TCP/UDP listeners | 14 (sshd, LLMNR 5355 and mDNS 5353 on all interfaces; DNS stub and chrony on loopback) | 8 (sshd on all interfaces, development variant only; DNS stub and chrony on loopback) |
| Processes | 153 | 150 |
| Failed units | 0 | 0 |
| SELinux denials per boot | 3 (BUG-1) | 0 |
| SELinux permissive domains in the policy | 31 | 31 |
| Setuid/setgid files, files with capabilities | 17, 8 | 17, 8 |

The baseline is not lighter than stock Fedora: firewalld and auditd were added, and
they cost about 40 to 60 MiB and up to 0.4 s of startup. The number of running services is
the same because two were added and two (avahi, sssd-related) removed. Memory in use is
above the blueprint's provisional 400 MiB budget for V-12; that budget is revisited in
P1-17.

Nothing has been verified on a local workstation or on physical hardware.

## 6. Known bugs

| ID | Description | Impact | Plan |
|---|---|---|---|
| BUG-1 | Closed for disks built by this repository (`c3308a8`, run 43557838924: zero denials). Every boot logged 3 SELinux denials: `bootloader-update.service` runs `bootupctl` (domain `bootupd_t`, declared permissive by Fedora), which reads `/sysroot/.bootc-aleph.json` and files under `/sysroot/boot`. 344 files written at the end of the installation (the whole `/boot/grub2` tree, `/boot/bootupd-state.json`, `/.bootc-aleph.json`) carried the catch-all type `default_t`. Cause: on an SELinux system they inherit `boot_t` and `root_t` from their directories, which is what Fedora's policy lets `bootupd_t` use; our disks are installed on a GitHub runner whose kernel has no SELinux, so nothing is inherited. Supported by the result (giving them the parents' labels removes every denial), not by a comparison install on an SELinux host. A first attempt with file-context rules in a policy module had no effect (run 43554934333) and was removed. | None left in our disks. A disk installed by other means on a host without SELinux would still log the denials (nothing is blocked; the domain is permissive). | `scripts/fix-install-labels`, run by `scripts/build-disk` after the installation, gives every `default_t` file outside the ostree repository the label of its parent directory. No policy change. An installer that runs on an SELinux system (Phase 6) should not need it. Worth reporting to bootc upstream (owner's decision; text can be prepared). |
| BUG-2 | Closed (`bf592c8`). The image identified itself as Fedora; `os-release` and the hostname now say AEGIS. The initramfs part remains as BUG-5. | | |
| BUG-3 | At power-off the console shows "Failed to unmount /run/shutdown/mounts/...: Device or resource busy" and "Not all file systems unmounted, 1 left" before "Syncing filesystems" and "Power down". Seen on `aegis-base` in run 43546633024. | None observed: the following boot shows no filesystem recovery (V-02). Looks like the physical root that backs the running deployment. | Confirm the cause; re-check after the sealed boot chain changes the mount layout (P1-11). |
| BUG-4 | Closed. `podman build` 4.9 left an empty `/etc/hostname` in the image; the image now ships that file with the static hostname `aegis`. | | |
| BUG-6 | `ausearch -ts boot` returns nothing on the test VM although the audit log is being written (run 43554108533). | Tests that query the audit log by "since boot" would silently see no events. | The SELinux tests read the whole audit log and the journal and filter by time themselves. Cause not yet investigated. |
| BUG-5 | The initramfs is the one built by Fedora. It contains Fedora's `os-release`, so early boot identifies itself as Fedora and sets the hostname `fedora` until the real system applies `/etc/hostname`. | Cosmetic in M2. | The initramfs is regenerated when the UKI is built for the sealed boot chain (P1-11). |
| BUG-7 | The base image pin does not last. quay.io stopped serving the digest resolved on 2026-11-13 by 2026-11-15 ("manifest unknown", build run 43716522192); the repository has only the moving tags `45` and `45-<arch>` (probe run 43717628014). | No commit can be rebuilt once its pin is gone, so results cannot be reproduced later (R-02) and every build fails until the pin is renewed. | Pin renewed to the digest of 2026-11-15. Lasting fix: keep a copy of the base image under the project's control (owner decision, section 9), then pin to that copy. Part of P1-15. |

## 7. Security limitations

`docs/architecture/security-baseline.md` lists what the M2 image provides, with the test
for each statement, and what it does not. In short:

- The image boots with the ostree backend and GRUB, **without** Secure Boot, without a
  sealed root, unsigned, unencrypted, and with no update source. Someone with access to
  the disk can change it. Sealed boot is M3; signing and updates are M4.
- 31 SELinux domains are permissive in Fedora's policy
  (`tests/golden/base/selinux-permissive-domains.txt`); programs in them are logged, not
  confined. `bootupd_t` is the one that runs at every boot. Root can switch SELinux to
  permissive at runtime.
- Console and SSH access can be granted from outside the image through systemd
  credentials in the firmware's SMBIOS strings. This is how the test harness logs in and
  is equivalent to console access; whether a release image should honour them is a
  Phase 2 decision.
- Reverse-path filtering is strict on every interface except the one that carries the
  default route, which is loose. Shown by experiment in run 43554108533: after forcing
  the value to strict, `nmcli device reapply` set it back to loose. NetworkManager
  relaxes it on purpose for interfaces with a default route. Filtering is never off.
- The release variant (`aegis-base`) is tested from outside only (console output, power
  button, closed SSH port, image manifests). Runtime checks that need a shell run on the
  development variant, which differs by the recorded delta (sshd and the SELinux
  self-test).
- The SELinux label correction (BUG-1) applies to disks built by this repository.
- The disk has a BIOS boot partition and a 512 MiB ESP because `bootc install to-disk`
  was run with `--generic-image`; BIOS boot support is not wanted in the final design.
- Package goldens hold names, not versions; packages are not version-locked until P1-15.
- Planned Phase 1 limitations (see blueprint section 11): no disk encryption, throw-away
  signing keys, no automatic rollback on failed boot, no application sandboxing, `/etc`
  and `/var` are not integrity-protected.
- Nothing has been tested on physical hardware.

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

Open decisions:

- **Where to keep a copy of the base image (BUG-7).** Recommended: mirror the pinned
  `fedora-bootc` image into the repository's GitHub Container Registry
  (`ghcr.io/ben10-games/...`) from a workflow and pin to that copy. Needs the workflow
  permission `packages: write` and counts against the account's package storage. Until
  decided, the pin must be renewed by hand each time it disappears, and old commits
  cannot be rebuilt.
- Whether the `windows-launch` job may install QEMU from the Chocolatey community
  repository on the hosted Windows runner (test only).

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

`quay.io/fedora/fedora-bootc:45` on 2026-11-15 is
`sha256:17227a17c0bb9222918881e27f254e219eb3808ceb4399e26322bbd2e77932bc` (probe run
43717628014): same bootc, kernel, systemd, selinux-policy and openssh versions and the
same package count (540) as below.

`quay.io/fedora/fedora-bootc:45` on 2026-11-13
(`sha256:42259b1db41a7f792a19cfd28e0c66e3e415392109a7d7095f292ad1e2a56453`):

- bootc 1.17.1, kernel 7.3.3-300.fc45, systemd 262.1, selinux-policy-targeted 45.24,
  openssh-server 10.5p1, 540 packages.
- `bootupd` 0.3.2 is installed (must be removed for the sealed path, P1-11).
- Not installed: `systemd-boot-unsigned`, `systemd-ukify`, `firewalld`, `audit`.

GitHub quirk: a workflow with a `paths` filter did not start on the first push of a new
branch; it started on the next push that touched a matching path.

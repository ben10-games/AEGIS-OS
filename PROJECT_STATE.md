# AEGIS OS — project state

This file is the single source of truth for what exists and what has been verified.
It is updated in the same commit as the work it describes. A test is listed as verified
only if it actually ran and passed, with the commit and where it ran.

## 1. Resume here

- **Branch:** `claude/aegis-os-architecture-ayxptj`
- **Phase / milestone:** Phase 1, milestone M2 (baseline configuration) in progress.
  M0 and M1 are complete. The approved M2 plan has eight increments; see section 2.
- **Next task:** finish increment 7 of M2 (P1-09: SELinux verification and the BUG-1
  fix), then the before/after record and baseline documents. Do not start M3 before M2
  is complete.
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

### Session handoff, recorded 2026-11-14T04:28Z (before a context compaction)

**Where the work stands**

- M2 is **not complete**. Increments 1 to 6 are done and green (`e378b1e`, run 43554108533).
  Increment 7 (P1-09, SELinux) is in its second iteration.
- `ad224f0` (run 43556115948) failed in "Build disk images": `scripts/fix-install-labels`
  looked for the root partition with `lsblk`, which reports no partition names inside a
  container (no udev database). The installation itself had completed. Fixed in the
  next commit: the partition is found by its GPT type with `sfdisk --dump`.
- The previous commit `f635e02` (run 43554934333) passed 52 of 55 VM tests: the SELinux
  policy build, module load, file contexts and the enforcement self-test all work.
  The 3 failures were BUG-1 (install-time files still `default_t`).

**Next steps, in order**

1. Done: disk-build failure of run 43556115948 read and fixed (see above).
2. Get a green build; then V-08 is verified and P1-09 and M2 can be closed: write
   `docs/architecture/security-baseline.md` (draft exists, see below), the before/after
   measurements, and update sections 2, 4, 5 and 7 of this file.
3. Then the owner's follow-up request: local VM testing (see "Stashed work").

**Background tasks in this session**

| ID | Command | Output file | State |
|---|---|---|---|
| `b05590g4t` | `sleep 580; echo waited` (a timer started at about 04:20Z to wait for build run 43556115948; it does no work itself) | `/tmp/claude-0/-home-user-AEGIS-OS/ca6fec80-564a-5eee-b0bb-f1c9dc5a8c65/tasks/b05590g4t.output` | completed at about 04:30Z and prints `waited`. Nothing depends on its output: the run it was waiting for has already finished. |

No other background task is running. All earlier timers (`bwfgs821u`, `bdlwlhuho`,
`bb594qeg5`, `bm7je4dcn`, `bo7yr8u33`, `bzmk07uot`, `bjaidndj9`, `b520h0vwk`,
`bpv62na23`, `b75o97nmb`, `bj7905ers`, `b9lsncky1`, `b3572xvqm`, `bwg3ax6qz`,
`b2zudpz6t`, `bljmwy1ul`, `b13rmh7zz`, `br5bq05xg`) have completed. No build, VM or
other long-running process runs in this container; all builds run in GitHub Actions.

**Work that exists only in this container (not pushed)**

- `git stash` entry `stash@{0}` ("WIP on ... f635e02"): the complete draft of the
  local-VM deliverables requested by the owner. Apply with `git stash pop` once M2 is
  green. It contains: `LOCAL_VM_GUIDE.md`, `local-vm/run-aegis-vm.sh`,
  `local-vm/run-aegis-vm.ps1`, `scripts/export-qcow2`, `tests/vm/test_local_image.py`,
  and changes to `.github/workflows/build.yml` (export step, artifact
  `aegis-os-dev-qcow2` published on `workflow_dispatch` or when the head commit message
  contains `[publish-image]`, and a `windows-launch` job), `Makefile`,
  `scripts/run-vm-tests`, `scripts/summarize-results`, `tests/vm/conftest.py`.
  None of it has run in CI. The stash was made on `f635e02`; `scripts/summarize-results`
  changed again in `ad224f0`, so expect a small merge when popping.
- Draft of `docs/architecture/security-baseline.md`:
  `/tmp/claude-0/-home-user-AEGIS-OS/ca6fec80-564a-5eee-b0bb-f1c9dc5a8c65/scratchpad/security-baseline.md`.
  It assumes V-08 passes; check that before committing it.
- Local tags `p1-m0` and `p1-m1-first-boot` (tag pushes are refused with HTTP 403).

**Design decisions for the local-VM image (so they need not be re-derived)**

- The image is `aegis-dev` exported as compressed QCOW2 (zlib, for compatibility).
- No password or key in the image. Login is granted at launch through systemd
  credentials in SMBIOS strings: `agetty.autologin=root` and `login.noauth=yes` for the
  serial console, `ssh.authorized_keys.root` for SSH. Whether the console autologin
  credentials work on Fedora 45 is **untested**; the SSH credential is proven.
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
| P1-09 | SELinux enforcement validation | in progress | policy module, self-test and BUG-1 fix pushed |
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

| V-03 Kernel: one kernel in the image and it is the one running; not tainted; only allow-listed error messages | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-10 Networking: address and route from DHCP; name resolution through systemd-resolved; outbound fetch by name; listeners equal the golden list (harness DNS and HTTP servers, no internet; HTTP not HTTPS) | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-11 Firewall: firewalld active, default zone `aegis` with target DROP, drop verdict in the kernel ruleset; a listener outside the zone is unreachable from outside, with positive controls | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-19 Kernel arguments, lockdown in integrity mode, 31 sysctl values equal the golden lists; reverse-path filtering never off | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| Audit daemon attached to the kernel, auditing enabled, log written | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |

Not yet run: B-05 to B-07, V-04 to V-09, V-12 to V-16, V-18 (except the parts noted above), all R tests.

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
| BUG-1 | Every boot logged 3 SELinux denials: `bootloader-update.service` runs `bootupctl` (domain `bootupd_t`, declared permissive by Fedora), which reads `/sysroot/.bootc-aleph.json`. That file, `/sysroot/boot/grub2` and `/sysroot/boot/bootupd-state.json` carried the catch-all type `default_t`. Cause, by elimination: Fedora's policy lets `bootupd_t` read `root_t` and manage `boot_t`, which is what these files inherit from their directories when the installer runs on an SELinux system; our disks are installed on a GitHub runner whose kernel has no SELinux, so nothing is inherited. A first attempt with file-context rules in a policy module had no effect (run 43554934333) and was removed. Not proven by a comparison install on an SELinux host. | Nothing was blocked (the domain is permissive), but V-08 requires zero denials. | `scripts/fix-install-labels`, run by `scripts/build-disk` after the installation, gives every `default_t` file outside the ostree repository the label of its parent directory. No policy change. Limits: it fixes disks built by this repository; an installer that runs on an SELinux system (Phase 6) should not need it. Upstream report to bootc still to be written by the owner. |
| BUG-2 | The image still identifies itself as Fedora (`os-release`, hostname `fedora`). | Cosmetic. | M2 increment 3. |
| BUG-3 | At power-off the console shows "Failed to unmount /run/shutdown/mounts/...: Device or resource busy" and "Not all file systems unmounted, 1 left" before "Syncing filesystems" and "Power down". Seen on `aegis-base` in run 43546633024. | None observed: the following boot shows no filesystem recovery (V-02). Looks like the physical root that backs the running deployment. | Confirm the cause; re-check after the sealed boot chain changes the mount layout (P1-11). |
| BUG-4 | Closed. `podman build` 4.9 left an empty `/etc/hostname` in the image; the image now ships that file with the static hostname `aegis`. | | |
| BUG-6 | `ausearch -ts boot` returns nothing on the test VM although the audit log is being written (run 43554108533). | Tests that query the audit log by "since boot" would silently see no events. | The SELinux tests read the whole audit log and the journal and filter by time themselves. Cause not yet investigated. |
| BUG-5 | The initramfs is the one built by Fedora. It contains Fedora's `os-release`, so early boot identifies itself as Fedora and sets the hostname `fedora` until the real system applies `/etc/hostname`. | Cosmetic in M2. | The initramfs is regenerated when the UKI is built for the sealed boot chain (P1-11). |

## 7. Security limitations

- The M1 image is the stock Fedora bootc base plus identity metadata. It boots with the
  ostree backend and GRUB, **without** Secure Boot, without a sealed root, unsigned, and
  with no AEGIS hardening. The only demonstrated properties are: it boots, SELinux is
  enforcing, and `/usr` is read-only.
- `aegis-base` still has whatever services the Fedora base enables (including possibly
  sshd); the release-shaped service set is P1-07/P1-08.
- SELinux denials occur during boot (BUG-1); V-08 is not met.
- Reverse-path filtering is strict on every interface except the one that carries the
  default route, which is loose. Shown by experiment in run 43554108533: after forcing
  the value to strict, `nmcli device reapply` set it back to loose. NetworkManager
  relaxes it on purpose for interfaces with a default route. Filtering is never off.
- The firewall and audit daemons cost memory: about 529 MiB in use after boot, against
  472 MiB for the stock image.
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

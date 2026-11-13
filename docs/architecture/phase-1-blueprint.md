> **Status:** approved by the project owner on 2026-11-13. This is the approved text, unmodified.

> Deviations made during implementation are recorded in `PROJECT_STATE.md` and in the ADRs, not by editing this file.

# AEGIS OS — Phase 1 Engineering Blueprint

## Context

The repository (`ben10-games/AEGIS-OS`, branch `claude/aegis-os-architecture-ayxptj`) is empty: no commits, no files. This blueprint defines the foundation of AEGIS OS and an implementation-ready plan for Phase 1 (Core Foundation). Nothing has been built or modified. Every claim below is either verified in this session (marked **[verified]**), taken from upstream documentation read in this session (**[upstream]**), or an explicit assumption (**[assumption Ax]**) with a task that tests it.

**Verified facts about this Claude Cloud environment** (probed read-only on 2026-11-13):

| Capability | Result |
|---|---|
| `/dev/kvm`, vmx/svm CPU flags | Absent. No hardware virtualization; no boot testing here. |
| Container runtime | Docker client installed, **no daemon running**; podman, buildah, skopeo absent. |
| `quay.io`, `registry.fedoraproject.org`, `mirrors.`/`dl.`/`download.fedoraproject.org` | **Blocked by network policy** (proxy 403). Fedora base images and RPMs cannot be fetched. |
| `ghcr.io`, `registry-1.docker.io`, `github.com`, `pypi.org`, `archive.ubuntu.com` | Reachable. |
| QEMU, swtpm, OVMF, bootc, cosign, syft, just, shellcheck | Not installed. |
| Host | Ubuntu 24.04, root, 4 vCPU, 15 GiB RAM, ~31 GiB free disk. |

Consequence: Claude Cloud can author and statically verify everything, but **image builds and VM boot tests must run in GitHub Actions (primary) or on a local KVM machine (secondary)**. The plan is built around that.

---

## 1. Executive architectural decision

**AEGIS OS is a single derived Fedora bootc image (Fedora 45), built as an OCI container, deployed and updated by `bootc`, booted as a *sealed* image:**

> UEFI Secure Boot → signed systemd-boot → signed Unified Kernel Image (kernel + initramfs + command line containing the root filesystem's composefs digest) → composefs root with fs-verity enforcement → SELinux enforcing userspace.

Mutable state is confined to `/etc` and `/var`. Updates are signed OCI images applied as whole-image deployments with rollback. The stock Fedora kernel is used unmodified.

"Hybrid" is interpreted as *a Linux host combined with compatibility layers and virtual machines*, not a hybrid kernel. No new kernel is written.

**Why sealed, and why decide now.** bootc has two storage backends (ostree and composefs). Only the composefs backend supports sealed images and systemd-boot **[upstream]**, and there is no supported in-place migration between backends. Choosing after machines are installed would force reinstalls, so Phase 1 settles it while the installed base is zero. Upstream bootc (1.17.4 on `main`) now documents sealed images outside the "Experimental" section and covers the composefs backend with its stability guarantees for installs since 1.16.0 **[upstream]**. Fedora's own sealed Atomic Desktop images were still labelled test-only in April–May 2026, so this is a young path. It is therefore gated:

**Decision gate G1 (task P1-11).** Sealed mode is adopted only if, on the pinned `fedora-bootc:45` base, install → Secure Boot → upgrade → rollback → tamper-rejection all pass in a VM. If G1 fails, the fallback is the ostree backend with shim + GRUB (Fedora-signed), recorded in an ADR, with sealed mode revisited before Phase 6. The repository isolates the difference to one Containerfile stage and the disk-build flags.

**Places where I am not following the brief as written:**

- **macOS applications.** Running macOS in a VM on non-Apple hardware violates Apple's licence, and Darling (the only translation layer) is experimental and largely command-line. AEGIS will not ship macOS VM support. Darling gets an evaluation slot in Phase 3 as an untrusted-tier experiment, with no compatibility promise.
- **Custom desktop.** Writing a compositor from scratch is a multi-year project that would starve everything else. Phase 4 should build an original shell and design system on an existing Wayland compositor library. Phase 1 only keeps that door open (Wayland-only, no display-manager assumptions).
- **Encryption in Phase 1.** LUKS2 + TPM2 enrollment belongs with the installer and key-recovery design. bootc upstream recommends setting up encryption outside bootc and installing with `bootc install to-filesystem`; its built-in `tpm2-luks` path is documented as fragile **[upstream]**. Phase 1 disk images are unencrypted development artifacts; Phase 2 adds encryption without changing the layout.
- **Automatic rollback on failed boot.** The composefs backend does not yet configure systemd boot counting **[upstream]**. Phase 1 delivers and tests *manual* rollback; automatic health-checked rollback is a Phase 2 item.

---

## 2. Selected technology stack and rationale

### 2.1 Foundation comparison

| Candidate | Strengths | Disqualifying weakness for AEGIS |
|---|---|---|
| **Fedora bootc (selected)** | SELinux enforcing with the most mature policy; sealed images (UKI + composefs + fs-verity); OCI-native build and update; current kernel and Mesa; rollback built in | Sealed path is young; Fedora's 13-month release life forces regular rebases |
| Universal Blue / Bazzite as base | Best out-of-box gaming; signed NVIDIA modules | Adds a third-party build chain to the trusted base; built on the ostree backend. Borrow techniques, do not inherit |
| openSUSE Aeon / MicroOS | TPM-backed encryption, btrfs snapshot rollback | Package-transaction model, not verified images; no fs-verity root integrity; SELinux policy newer |
| NixOS | Strongest reproducibility | No supported SELinux; Secure Boot is community-maintained; mutable store without verity |
| Ubuntu Core (desktop) | Signed snaps, TPM encryption | AppArmor only; snap-store-centred; desktop variant immature |
| Arch + A/B updater (SteamOS model) | Gaming performance | No mandatory access control; rolling release without reproducible snapshots; build the whole update system yourself |
| mkosi + systemd-sysupdate + dm-verity | Cleanest measured-boot design | You become the distribution maintainer; fixed A/B partitions; small ecosystem; SELinux less travelled |

Fedora bootc is the only candidate that delivers mandatory access control, a cryptographically verified root filesystem, image-based updates with rollback, and a current gaming-capable graphics stack **from one upstream**, with the derivation step being an ordinary container build.

### 2.2 Stack

| Layer | Choice | Rationale |
|---|---|---|
| Base image | `quay.io/fedora/fedora-bootc:45`, pinned by digest and mirrored to GHCR | Fedora 45 released 2026-11-03; digest pin plus mirror makes the input immutable and available |
| Kernel | Stock Fedora kernel, no patches, no out-of-tree modules in Phase 1 | Fedora's update and CVE stream; any change must show measured benefit (Phase 5) |
| Deployment | bootc, composefs backend, sealed (G1) | See §1 |
| Bootloader | systemd-boot + UKI | Required for sealed images; removes GRUB's large attack surface |
| Root filesystem | btrfs | fs-verity support; Fedora desktop default; snapshots and reflinks useful later for user-data recovery and disposable VM disks. Fallback: ext4 |
| Init / services | systemd, default-deny unit presets, golden manifest of enabled units | Minimal background activity, auditable |
| Mandatory access control | SELinux enforcing, Fedora targeted policy; custom modules built in-image | Meets the requirement without inventing a policy |
| Firewall | firewalld (nftables backend), default zone dropping inbound | Integrates with NetworkManager, podman and libvirt needed in Phase 3; overhead measured in Phase 1 |
| Network | NetworkManager + systemd-resolved | Needed by the eventual desktop; already in base |
| Image build | buildah/podman inside a pinned **builder container** | Same tool versions in CI and locally |
| Disk build | `bootc install to-disk --via-loopback` (Phase 1); `systemd-repart` + `bootc install to-filesystem` (Phase 2, LUKS) | Uses the real installer code path; no extra image-builder dependency |
| Package pinning | `rpms.in.yaml` → generated `rpms.lock.yaml` (NEVRA + sha256) via `rpm-lockfile-prototype` | Deterministic inputs; reviewed diffs |
| Signing | cosign for images; `sbsign` via `ukify` for UKI and bootloader | Standard, verifiable by containers-policy and firmware |
| SBOM / scanning | syft (SPDX), grype (report-only in Phase 1) | Supply-chain visibility |
| Task runner | `just`; logic in small linted scripts | One entry point for humans, CI and Claude |
| Tests | pytest: container-level tests + QEMU/OVMF/swtpm VM harness | Structured pass/fail, JUnit output |
| CI | GitHub Actions on hosted Linux runners with KVM **[assumption A1]** | Only place builds and boots can run for cloud sessions |
| Registry | `ghcr.io/ben10-games/aegis-os` | Reachable from CI and from Claude Cloud |

**Phase 1 stores no long-lived signing secrets.** Secure Boot and cosign keys are generated per CI run (and per developer under a git-ignored `.secrets/`), used, and discarded. A real key hierarchy is a Phase 2 deliverable.

### 2.3 Roadmap and phase acceptance criteria

| Phase | Measurable exit criteria |
|---|---|
| 1 Core Foundation | §11 |
| 2 Security Hardening | LUKS2 + TPM2 (PIN option) unlock tested with swtpm; persistent key hierarchy with offline root; signed-update enforcement with production keys; automatic rollback on failed boot; application sandbox tiers enforced by policy; admin/user separation; audit rules; CIS-style scan with documented exceptions |
| 3 Application Compatibility | Flatpak apps run sandboxed; Steam + Proton launch a reference title; Wine apps run confined with no home-directory access; disposable VM launches untrusted executable with no host file/credential access (tested); NVIDIA signed modules load under Secure Boot |
| 4 Custom Desktop | Session starts on Wayland under SELinux enforcing; frame-time and input-latency budgets met; settings and system apps pass accessibility and crash-rate thresholds |
| 5 Optimization | Every merged tuning has before/after numbers; boot, idle RAM, idle wakeups, game frame-time targets met against Phase 1 baselines |
| 6 Hardware Deployment | Installer with encryption on a defined hardware matrix; Secure Boot key enrollment path; update, rollback and recovery proven on physical machines |

---

## 3. System architecture diagram

```
                         BUILD (CI or local, inside pinned builder container)
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │ fedora-bootc@sha256 ──► rootfs stage ──► split kernel ──► ukify + sbsign ──► OCI  │
 │ rpms.lock.yaml ───────►  (config in     (bootc container   (composefs digest      │
 │ image/rootfs overlay ─►   /usr/lib)      split-kernel…)     in UKI cmdline)       │
 │                                                                  │                │
 │                 SBOM (syft) ◄── cosign sign ◄────────────────────┘                │
 └────────────────────────────┬─────────────────────────────────────────────────────┘
                              ▼
                   ghcr.io/ben10-games/aegis-os  ──────────────┐ signed updates
                              │ bootc install                  │ (bootc upgrade)
                              ▼                                ▼
 RUNTIME ───────────────────────────────────────────────────────────────────────────
  Firmware (UEFI Secure Boot, TPM2)                    trust anchor, not verifiable by us
     │ verifies signature
  systemd-boot  (ESP, signed)
     │ verifies signature
  UKI = kernel + initramfs + cmdline{composefs.digest=…}   measured into TPM PCR 11
     │ initramfs mounts root only if digest matches (fs-verity enforced)
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ /  composefs, read-only, verified   (/usr, vendor config in /usr/lib)    │
  │ /etc  local configuration (mutable)      /var  state, /var/home (mutable)│
  │ [Phase 2: btrfs inside LUKS2, TPM2-bound]                                │
  ├──────────────────────────────────────────────────────────────────────────┤
  │ systemd (default-deny presets) · SELinux enforcing · firewalld · auditd  │
  ├───────────────┬────────────────────┬──────────────────┬──────────────────┤
  │ Tier 0        │ Tier 1             │ Tier 2           │ Tier 3           │
  │ OS image      │ Native apps        │ Compatibility    │ Untrusted        │
  │ (sealed)      │ Flatpak + portals, │ Steam/Proton,    │ disposable KVM   │
  │               │ podman             │ Wine in sandbox  │ VM, no host data │
  │  Phase 1      │  Phase 3           │  Phase 3         │  Phase 3         │
  └───────────────┴────────────────────┴──────────────────┴──────────────────┘
```

---

## 4. Security threat model and trust boundaries

### 4.1 Attackers and capabilities

| Attacker | Realistic capabilities | Primary controls | Phase |
|---|---|---|---|
| Remote network | Scans, exploits listening services, tampers with traffic and update transport | No listening services by default; inbound drop; signed updates verified independent of transport | 1 |
| Malicious application (native) | Code execution as the user; reads user files; attempts privilege escalation and persistence | Immutable verified `/usr`; SELinux; sandbox tiers; no setuid growth (golden list) | 1 partial, 2–3 |
| Malicious download (Windows EXE, script) | Runs under Wine/Proton with the same rights as that sandbox; Wine is **not** a boundary | Tier 2 sandbox with no home or credential access; Tier 3 disposable VM for untrusted files | 3 |
| Compromised dependency | Malicious RPM, base image, CI action or build tool | Digest-pinned base, locked RPMs with checksums and GPG, SHA-pinned actions, SBOM, reviewed input-bump PRs, reproducibility check | 1 |
| Physical, device off (theft, evil maid) | Reads or modifies disk; replaces boot files | Secure Boot + sealed root detect OS tampering (Phase 1, VM-proven); LUKS2 + TPM2 protect data (Phase 2); hardware proof Phase 6 | 1, 2, 6 |
| Physical, device on or suspended | DMA, cold boot, bus sniffing | Partial only: kernel lockdown, IOMMU, TPM+PIN. Stated limitation | 2, 6 |

**Out of scope (stated, not solved):** firmware or hardware implants; compromise of Fedora's signing infrastructure (detectable only after the fact via pinning and review); kernel zero-days (mitigated, never excluded); a user who knowingly grants a malicious app broad permissions; an attacker holding the user's unlock credentials. AEGIS will never claim immunity from malware.

### 4.2 Trust boundaries

1. **Firmware ↔ boot chain** — Secure Boot keys. Phase 1 uses ephemeral test keys in OVMF.
2. **Boot chain ↔ OS image** — the composefs digest in the signed UKI. Anything in `/usr` is trusted because it was built and signed by the pipeline.
3. **OS image ↔ mutable state** — `/etc` and `/var` are *not* integrity-protected. They are the persistence surface. Rule from Phase 1: all AEGIS configuration ships in `/usr/lib`; the image writes nothing to `/etc`, so any `/etc` content is local drift and can be diffed. Restricting execution from mutable locations (SELinux, and possibly the kernel's Integrity Policy Enforcement) is Phase 2 research.
4. **System ↔ user session** — privilege separation, polkit, no password-less root. Phase 2.
5. **User session ↔ application** — Tier 1/2 sandboxes. Phase 3.
6. **Host ↔ VM** — Tier 3; QEMU confined by SELinux sVirt, unprivileged, no shared folders or credentials by default. Phase 3.
7. **Build pipeline ↔ artifacts** — whoever controls CI and keys controls the OS. Phase 1: minimal workflow permissions, pinned actions, no stored secrets. Phase 2: offline root key.

### 4.3 Software trust tiers (fixed in Phase 1, implemented in Phase 3)

| Tier | Contents | Isolation | Access to user data and credentials |
|---|---|---|---|
| 0 | OS image | Verified, immutable | n/a |
| 1 | Vetted native apps | Flatpak sandbox + portals; SELinux | By explicit grant |
| 2 | Approved compatibility apps (Steam, Proton, Wine) | Sandbox *around* Wine; own data directory | None by default; compromise of the sandbox is assumed possible |
| 3 | Anything untrusted, any format | Disposable KVM VM, ephemeral disk, isolated or no network | None; explicit one-way file hand-off only |

---

## 5. Boot, filesystem, and update architecture

**Boot chain (target, after G1).** OVMF/UEFI with Secure Boot → `systemd-bootx64.efi` (signed) → UKI in `EFI/Linux/` (signed; built by `bootc container ukify`, which computes the composefs digest and reads kernel arguments from `/usr/lib/bootc/kargs.d`) → initramfs `bootc-root-setup.service` mounts root only if the digest matches. `bootupd` is removed from the image; its presence would select GRUB **[upstream]**. Physical-hardware key enrollment (own keys versus shim + MOK) is a Phase 6 decision recorded as an open ADR.

**Kernel arguments (Phase 1, low-risk set, each justified in an ADR):** `lockdown=integrity`, `slab_nomerge`, `init_on_alloc=1`, `page_alloc.shuffle=1`, `randomize_kstack_offset=on`, `vsyscall=none`, `audit=1`. Deliberately *not* in Phase 1: `init_on_free=1`, `nosmt`, `debugfs=off`, `mitigations` changes — each has a performance or compatibility cost that must be measured first.

**Sysctl baseline:** `kernel.kptr_restrict=2`, `kernel.dmesg_restrict=1`, `kernel.kexec_load_disabled=1`, `kernel.yama.ptrace_scope=1`, `kernel.unprivileged_bpf_disabled=1`, `net.core.bpf_jit_harden=2`, reverse-path filtering, no ICMP redirects or source routing. Unprivileged user namespaces stay enabled: every sandbox in Tiers 1–2 depends on them; per-domain restriction via SELinux is Phase 2.

**Disk layout (GPT):**

| Partition | Size | Filesystem | Notes |
|---|---|---|---|
| ESP | 2 GiB | vfat | systemd-boot plus UKIs for booted, staged and rollback deployments |
| root | remainder | btrfs (zstd:1, noatime) | composefs repository, `/etc`, `/var`. Phase 2: inside LUKS2 |

No separate `/boot` in sealed mode. Dual-boot machines with a small shared ESP will use an XBOOTLDR partition (supported by bootc) in Phase 6.

**Runtime filesystem:** `/` read-only composefs; `/usr` immutable; `/etc` and `/var` persistent and writable; `/home` → `/var/home`; `/tmp` tmpfs. bootc defaults are followed, not reinvented.

**Updates:** `bootc upgrade` pulls a new image from GHCR, verifies the cosign signature against the public key shipped in the image (`/etc/containers/policy.json` default `reject`, AEGIS namespace `sigstoreSigned`), stages it, and activates on reboot. Two independent checks protect an update: the registry signature at download and the Secure Boot signature on its UKI at boot. `bootc rollback` returns to the previous deployment. `bootc-fetch-apply-updates.timer` is disabled in Phase 1 because it reboots automatically; update policy is a Phase 2 design. Whether signature policy is enforced identically on the composefs backend is **[assumption A5]**, tested by V-15.

**Image variants:** `aegis-base` (release-shaped: no SSH, root locked, no users) and `aegis-dev` (`FROM aegis-base` plus SSH with key-only login and a self-test SELinux module). The VM's SSH key is injected at launch through a systemd credential on the QEMU command line **[assumption A6]**, so no key is ever baked into an image.

---

## 6. Build system and repository structure

**Build flow** (`just build`): start builder container → resolve base digest from `image/base.lock` → `rootfs` stage installs locked RPMs with weak dependencies off, copies `image/rootfs/`, applies presets, runs `bootc container lint --fatal-warnings` → `split` stage → `sealed-uki` stage signs with keys passed as build secrets (never in a layer) → final image with OCI labels (revision, version, source) → SBOM → sign.

**Reproducibility levels** (honest targets):

- **R-01 Input determinism (required):** same commit ⇒ identical base digest, RPM set and builder digest.
- **R-02 Content determinism (required; waivable only with your written sign-off):** two clean builds ⇒ identical composefs digest.
- **R-03 Bit-for-bit OCI digest (informational in Phase 1):** known upstream gaps exist (for example differing `.pyc` files in bootc base images).

**Input updates** are a scheduled workflow that opens a branch with a refreshed base digest and lockfile; it merges only after the full suite passes. This is the same mechanism that later carries security updates.

**Repository layout:**

```
AEGIS-OS/
├── README.md  CLAUDE.md  PROJECT_STATE.md  Justfile  .gitignore  .editorconfig
├── image/
│   ├── Containerfile              # rootfs → split → sealed-uki → final
│   ├── Containerfile.dev          # FROM aegis-base: sshd, self-test policy
│   ├── base.lock                  # base image reference by digest
│   ├── packages/rpms.in.yaml  rpms.lock.yaml
│   └── rootfs/usr/lib/            # systemd presets and drop-ins, sysctl.d, tmpfiles.d,
│                                  # bootc/kargs.d, bootc/install, firewalld, containers policy
├── policy/
│   ├── selinux/                   # custom modules (self-test in Phase 1)
│   └── containers/                # policy.json, registries.d templates
├── build/
│   ├── builder/Containerfile      # pinned toolchain image
│   └── disk/                      # layout definitions for disk images
├── scripts/                       # build-image, build-disk, dev-keys, run-vm, probe-env, bump-inputs
├── tests/
│   ├── static/                    # repo rules: pinned actions, state-file schema, ADR index
│   ├── image/                     # container-level tests
│   ├── vm/                        # harness (qemu, ovmf vars, swtpm, ssh) and tests
│   ├── golden/                    # packages, enabled units, setuid files, sockets, sysctl
│   ├── baselines/phase1.json      # measured metrics and budgets
│   └── repro/                     # double-build comparison
├── docs/
│   ├── architecture/              # this blueprint, threat model, security baseline
│   ├── adr/                       # 0000-template and numbered decisions
│   ├── development/               # cloud workflow, local KVM workflow
│   └── operations/                # recovery, rollback, maintenance, key handling
└── .github/workflows/             # lint, build, vm-test, update-inputs
```

**Initial ADRs:** 0001 Fedora bootc foundation · 0002 single image, two variants · 0003 stock kernel policy · 0004 sealed composefs backend (provisional until G1) · 0005 btrfs root · 0006 build-in-container and input pinning · 0007 ephemeral keys in Phase 1 · 0008 firewalld · 0009 trust tiers · 0010 CI as primary verification environment · 0011 macOS scope · open: hardware Secure Boot enrollment, custom minimal base versus stock `fedora-bootc`.

**`PROJECT_STATE.md` specification** (updated in the same commit as any change it describes):

1. **Resume here** — next task ID, branch, last green CI run URL, exact commands to continue.
2. **Status** — phase, milestone, table of tasks (todo / in progress / done / blocked) with commit SHAs.
3. **Architecture decisions** — ADR index with status.
4. **Completed milestones** — tag, date, evidence link.
5. **Verified tests** — test ID, last pass commit, where it ran (CI / local). A test is listed only if it actually ran and passed.
6. **Known bugs.**
7. **Security limitations** — what is not yet protected.
8. **Assumptions** — A1…An with state: open / confirmed / refuted.
9. **Outstanding tasks and open decisions for the owner.**
10. **Environment notes** — cloud capability probe results, CI quirks.

`CLAUDE.md` holds the standing rules for any model: read `PROJECT_STATE.md` first; never commit secrets; never claim a test passed without a run; one task per commit series; CI is the source of truth.

---

## 7. Cloud and local development environments

| Environment | Can do | Cannot do |
|---|---|---|
| **Claude Cloud** | Author all files; run static tier (linters, secret scan, harness unit tests); commit and push; read CI results through GitHub tools | Build images, pull Fedora content, boot VMs (unless you later allow the Fedora hosts *and* a container daemon proves startable — not assumed) |
| **GitHub Actions** (primary verification) | Build in the builder container, create disk images, boot with KVM + OVMF + swtpm, run all tiers, publish to GHCR | Physical hardware, real TPM, real firmware |
| **Local Linux + KVM** (optional, recommended) | Everything CI does via the same `just` targets; interactive debugging with a serial console | — |
| **Physical hardware** | Not used in Phase 1 | — |

**Cloud development loop:** edit → `just lint` and static tests locally → small commit → push → CI runs build and VM tiers → Claude reads job results and logs → fix or mark the test verified in `PROJECT_STATE.md`. Workflows trigger on pushes to every branch; publishing to GHCR happens only from the default branch.

**Safety:** all risky operations (loop devices, privileged containers, disk writes) happen inside CI runners or a builder container against image files, never against a host disk. `scripts/build-disk` refuses any target that is a block device.

---

## 8. Ordered implementation tasks

Location tags: **[C]** fully doable in Claude Cloud · **[CI]** authored in cloud, verified only in GitHub Actions or locally · **[L]** local KVM optional. No Phase 1 task needs physical hardware.

**Milestone M0 — repository and tooling**

**P1-00 Environment probe** [C + CI]
- Objective: record real capabilities of cloud and CI runners; confirm A1.
- Files: `scripts/probe-env`, `.github/workflows/probe.yml` (manual trigger).
- Depends on: nothing. Result: probe output stored in `PROJECT_STATE.md` §10.
- Verify: CI job prints `/dev/kvm` present and usable, free disk, podman/docker versions.
- Failure: no KVM on hosted runners → switch VM tier to a self-hosted or local runner; document; static and build tiers proceed.

**P1-01 Repository scaffold** [C]
- Objective: governance and continuity files.
- Files: `README.md`, `CLAUDE.md`, `PROJECT_STATE.md`, `.gitignore` (includes `.secrets/`, `out/`), `.editorconfig`, `docs/architecture/phase-1-blueprint.md` (this document), `docs/adr/0000-template.md`, ADRs 0001–0011.
- Depends on: none. Verify: `tests/static` schema check for state file and ADR index passes.
- Failure: none significant; pure documentation.

**P1-02 Static tooling and lint workflow** [C]
- Objective: one command for all static checks.
- Files: `Justfile`, lint configs, `tests/static/*`, `.github/workflows/lint.yml`.
- Components: shellcheck, hadolint, yamllint, actionlint, ruff, gitleaks; check that all actions are pinned by commit SHA.
- Depends on: P1-01. Verify: `just lint` exits 0 locally and in CI; a seeded fake key in a scratch branch is caught by gitleaks.
- Failure: a tool unavailable in cloud → run it only in CI and note it.

**P1-03 Builder container** [CI]
- Objective: pinned toolchain (buildah, podman, skopeo, bootc, systemd-ukify, sbsigntools, qemu, edk2-ovmf, swtpm, virt-firmware, cosign, syft, grype, just, pytest).
- Files: `build/builder/Containerfile`, `scripts/in-builder`.
- Depends on: P1-02. Verify: CI builds it; `in-builder <tool> --version` succeeds for each tool; digest recorded.
- Failure: a package missing in Fedora 45 → fetch a checksum-pinned release binary.

**Milestone M1 — first boot (smallest verifiable system)**

**P1-04 Minimal derived image** [CI]
- Objective: `aegis-base` = pinned `fedora-bootc:45` plus labels only.
- Files: `image/Containerfile`, `image/base.lock`, `scripts/build-image`, `.github/workflows/build.yml`.
- Depends on: P1-03. Verify: B-01. Record the `bootc --version` found in the base (needs ≥ 1.16 for G1).
- Failure: base tag missing or pull blocked → check tag name on the registry; do not substitute another distribution.

**P1-05 Disk image** [CI]
- Objective: raw and qcow2 from the image via `bootc install to-disk --via-loopback`.
- Files: `scripts/build-disk`, `build/disk/phase1.toml`.
- Depends on: P1-04. Verify: B-08.
- Failure: loop devices unavailable in the nested container → run the install step directly on the runner with podman; keep the script's interface.

**P1-06 VM harness and first boot test** [CI, L]
- Objective: boot the disk under QEMU + OVMF, reach a shell, shut down cleanly.
- Files: `tests/vm/harness/{qemu.py,ssh.py,firmware.py}`, `tests/vm/test_boot.py`, `scripts/run-vm`, `.github/workflows/vm-test.yml`; `image/Containerfile.dev`.
- Depends on: P1-05. Verify: V-01, V-02. **Checkpoint tag `p1-m1-first-boot`.**
- Failure: credential-based key injection fails (A6) → dev image accepts a per-build public key passed as a build argument; serial log is always uploaded as an artifact.

**Milestone M2 — baseline configuration**

**P1-07 Base and dev variant split with golden manifests** [CI]
- Files: `tests/golden/*`, `tests/image/test_manifests.py`.
- Depends on: P1-06. Verify: B-02, B-03, B-04. Golden files change only by explicit commit.

**P1-08 Operating system baseline** [CI]
- Objective: presets, journald limits, chrony, NetworkManager, firewalld zone, sysctl, kernel arguments, locked root, update timer disabled.
- Files: `image/rootfs/usr/lib/**`.
- Depends on: P1-07. Verify: V-03, V-10, V-11, V-17, V-19, V-20.
- Failure: a default-deny preset breaks boot → harness boots the previous image; bisect by re-enabling units one at a time.

**P1-09 SELinux enforcement validation** [CI]
- Objective: prove enforcing mode works and the policy build pipeline exists.
- Files: `policy/selinux/aegis_selftest.{te,fc}`, `tests/vm/test_selinux.py`.
- Depends on: P1-08. Verify: V-08.
- Failure: denials at boot → fix labels or configuration; never switch to permissive to pass.

**Milestone M3 — sealed boot chain (gate G1)**

**P1-10 Ephemeral key tooling** [C + CI]
- Files: `scripts/dev-keys` (Secure Boot PK/KEK/db and cosign pair into `.secrets/` or the CI workspace), `tests/static/test_secrets_ignored.py`.
- Depends on: P1-02. Verify: keys never appear in `git status`; B-05.

**P1-11 Sealed image: UKI, systemd-boot, composefs — gate G1** [CI]
- Objective: implement the upstream three-stage sealed build; remove `bootupd`; add systemd-boot; ship `loader.conf`.
- Files: `image/Containerfile` (split and sealed-uki stages), `image/rootfs/usr/lib/bootc/{kargs.d,install}/…`, `tests/vm/harness/firmware.py` (enroll keys into OVMF variables), ADR-0004 finalised.
- Depends on: P1-08, P1-10. Verify: B-06, V-04, V-06, then V-13/V-14 once P1-13 lands.
- Failure: any G1 criterion fails → file findings, switch to the ostree-backend fallback, mark ADR-0004 "fallback active", continue Phase 1; sealed-specific tests are then reported as *not met*, not skipped silently.

**P1-12 Tamper and negative boot tests** [CI]
- Files: `tests/vm/test_integrity.py`.
- Depends on: P1-11. Verify: V-05, V-07.

**Milestone M4 — updates**

**P1-13 Signing and signature policy** [CI]
- Files: `policy/containers/*`, `image/rootfs/…/containers/`, publish job in `build.yml` (default branch only, minimal permissions).
- Depends on: P1-10, P1-04. Verify: signature verifies with the run's public key; B-07.

**P1-14 Update and rollback tests** [CI]
- Objective: local registry in the test job serving v1, v2 (signed) and v3 (unsigned).
- Files: `tests/vm/test_update.py`, harness registry fixture.
- Depends on: P1-13, P1-11. Verify: V-13, V-14, V-15, V-09.
- Failure: policy not enforced on the composefs backend (A5) → record as a security limitation; the Secure Boot check on the UKI remains; raise upstream.

**Milestone M5 — supply chain and reproducibility**

**P1-15 Input pinning** [CI]
- Files: `image/packages/rpms.in.yaml`, `rpms.lock.yaml`, `scripts/bump-inputs`, `.github/workflows/update-inputs.yml`; base mirrored to GHCR by digest.
- Depends on: P1-08. Verify: R-01; a build with network restricted to the mirror and locked RPM URLs succeeds.
- Failure: locked RPMs disappear from Fedora mirrors → resolve against Fedora's updates-archive repository **[assumption A4]**, else cache RPMs as a GHCR artifact.

**P1-16 Reproducibility, SBOM, vulnerability report** [CI]
- Files: `tests/repro/test_double_build.py`, SBOM and grype steps.
- Depends on: P1-15, P1-11. Verify: R-02 (R-03 reported), B-07.
- Failure: digests differ → the test prints the differing paths; fix sources of nondeterminism (timestamps, caches); unresolved items need your sign-off.

**Milestone M6 — measurement, documentation, exit**

**P1-17 Metrics baseline** [CI]
- Files: `tests/vm/test_resources.py`, `tests/baselines/phase1.json`.
- Depends on: P1-11. Verify: V-12.

**P1-18 Operations and development documentation** [C]
- Files: `docs/operations/{recovery,rollback,maintenance,key-handling}.md`, `docs/development/{cloud-workflow,local-kvm}.md`, `docs/architecture/{threat-model,security-baseline}.md`.
- Depends on: P1-14. Verify: every command in the runbooks is exercised by a test or marked untested.

**P1-19 Phase 1 exit review** [CI]
- Objective: full suite from a clean checkout on one commit; update state file; tag `phase-1-complete`.
- Depends on: all. Verify: §11 checklist.

**Commit discipline:** Conventional Commits; one to three commits per task; each commit leaves `just lint` green; milestone tags `p1-m0` … `p1-m6`.

---

## 9. Test strategy and acceptance criteria

Tiers: **S** static (cloud and CI) · **B** image-level (CI/local) · **V** VM with KVM (CI/local) · **R** reproducibility (CI/local).

| ID | Test | Pass criterion |
|---|---|---|
| S-01 | Linters | All exit 0 |
| S-02 | Secret scan of repository | 0 findings |
| S-03 | Actions pinned | Every `uses:` references a 40-character commit SHA |
| S-04 | State file and ADR index | Required sections present; every ADR has a status |
| B-01 | Image construction | Build exits 0; `bootc container lint --fatal-warnings` exits 0; label `containers.bootc=1` present |
| B-02 | Package manifest | Sorted `rpm -qa` equals `tests/golden/packages.txt` |
| B-03 | Enabled units | Equals golden list |
| B-04 | Setuid/setgid files | Equals golden list |
| B-05 | No private key material in any image layer | 0 matches for key markers and for the run's key fingerprints |
| B-06 | Sealed structure | Exactly one UKI in `/boot/EFI/Linux`; no `bootupd`; no kernel or initramfs left in `/usr/lib/modules`; `sbverify` succeeds on UKI and bootloader; UKI command line has a strict `composefs.digest=` (no `?`) |
| B-07 | SBOM and signature | SPDX file lists the same package count as B-02; `cosign verify` exits 0 |
| B-08 | Disk image | qcow2 exists; GPT has ESP and root; root is btrfs |
| V-01 | Boot | SSH reachable ≤ 120 s; `systemctl is-system-running --wait` returns `running` ≤ 180 s; 0 failed units |
| V-02 | Shutdown | After `poweroff`, QEMU exits 0 ≤ 60 s; next boot shows no filesystem recovery |
| V-03 | Kernel | Running version equals the image's; kernel taint is 0; error-level kernel messages ⊆ allowlist |
| V-04 | Secure Boot | Reported enabled; `/sys/kernel/security/lockdown` shows `[integrity]` |
| V-05 | Tampered or unsigned UKI | VM does not boot; no SSH within timeout; firmware reports a verification failure |
| V-06 | Sealed root | `/proc/cmdline` carries the digest from the build; writing under `/usr` fails read-only; sampled objects report fs-verity enabled |
| V-07 | Offline modification of a root filesystem object | Boot stops, or reading the file fails; modified content is never returned |
| V-08 | SELinux | `getenforce` = Enforcing; 0 AVC denials since boot; self-test domain is denied its forbidden read and the denial is logged |
| V-09 | State boundaries | Sentinel files in `/etc` and `/var` survive reboot, update and rollback; booted image digest equals the built digest |
| V-10 | Networking | Lease obtained; name resolution works; HTTPS fetch from the harness server succeeds; listening sockets equal golden list (base: none off loopback) |
| V-11 | Firewall | firewalld active; default zone is the AEGIS zone; input policy drops |
| V-12 | Resources | Boot time, memory in use, task count, idle CPU over 60 s, image size all within budget. Provisional budgets (2 vCPU, 4 GiB, KVM): boot ≤ 30 s, memory ≤ 400 MiB, idle CPU ≤ 1 %, compressed image ≤ 2 GiB; replaced by measured baseline × 1.15 after the first green run |
| V-13 | Update | Signed v2 is staged; after reboot the booted digest is v2 |
| V-14 | Rollback | After `bootc rollback` and reboot the booted digest is v1 |
| V-15 | Unsigned update | `bootc upgrade`/`switch` exits non-zero; nothing staged |
| V-17 | Accounts | Root locked; SSH password authentication off; base has no regular users |
| V-18 | TPM (software) | TPM 2.0 device present; PCR 11 non-zero |
| V-19 | Sysctl and kernel arguments | Runtime values equal golden list |
| V-20 | Automatic update timer | Not enabled |
| R-01 | Input determinism | Two builds of one commit: identical base digest, RPM list, builder digest |
| R-02 | Content determinism | Identical composefs digest |
| R-03 | OCI digest equality | Reported; not gating |

A failed VM test always uploads the serial log, journal and JUnit report.

---

## 10. Risks, limitations, and mitigation strategies

| Risk or limitation | Impact | Mitigation |
|---|---|---|
| Sealed composefs path is young; Fedora's own sealed desktops were test-only in spring 2026 | Regressions, missing features | Gate G1; fallback backend; digest-pinned inputs so upgrades are deliberate |
| No automatic boot-failure rollback on the composefs backend | A bad update needs manual selection of the previous entry | Manual rollback tested in Phase 1; boot counting in Phase 2 |
| A1: hosted runners lack usable KVM (or repository is private with limited minutes) | No boot tests in CI | P1-00 checks first; fallback to local or self-hosted runner |
| Claude Cloud cannot build or boot | Slower feedback loop (push → CI) | Small commits; static tier in cloud; optional later allow-listing of Fedora hosts |
| Fedora mirrors drop old RPM versions | Locked builds break | Updates-archive repo (A4); RPM cache artifact |
| Bit-for-bit reproducibility gaps upstream | R-03 not met | R-01 and R-02 are the gates; differences listed, not hidden |
| Ephemeral keys in Phase 1 | Published images are not a real update trust root | Stated in README and state file; Phase 2 key ceremony |
| Unencrypted Phase 1 disks | No data-at-rest protection | Development VMs only; Phase 2 |
| Unconfined root can still change SELinux mode at runtime | Enforcement is not yet tamper-proof against root | Phase 2 policy hardening; sealed command line already prevents disabling at boot |
| `/etc` and `/var` unverified | Persistence surface | Vendor config only in `/usr`; drift check; Phase 2 execution controls |
| Fedora release cadence | Rebase every ~6–12 months | Automated input bumps with full test suite |
| Upstream documentation hosts were unreachable in this session (`bootc-dev.github.io`, `osbuild.org`) | Some flags unverified | bootc docs were read from the GitHub repository instead; exact flags confirmed against the pinned version during P1-04/P1-11 |
| Anti-cheat and some Windows software will never run | Compatibility expectations | Stated openly in Phase 3 scope |

**Open assumptions:** A1 hosted-runner KVM · A2 `fedora-bootc:45` ships bootc ≥ 1.16 · A3 `to-disk` supports btrfs with the composefs backend · A4 updates-archive availability · A5 signature policy enforced on the composefs backend · A6 SSH key injection via systemd credential.

**Decisions for you (none block the start):** repository licence; whether the repository is public (affects CI minutes and package visibility); whether you have a local Linux machine with KVM; whether to allow Fedora hosts in the Claude Cloud network policy later.

---

## 11. Explicit definition of Phase 1 completion

Phase 1 is complete when, on a single tagged commit:

1. All S, B and V tests in §9 pass in CI from a clean checkout, and R-01 and R-02 pass (or R-02 carries your recorded waiver).
2. Gate G1 has a recorded outcome in ADR-0004. If the fallback is active, V-04/05/06/07 and B-06 are listed as **not met** and Phase 1 is reported as *complete with the sealed chain outstanding*.
3. `aegis-base` and `aegis-dev` images, SBOM and signatures are published to GHCR from that commit.
4. Metrics baseline is committed in `tests/baselines/phase1.json`.
5. No secret exists in the repository or any image layer (S-02, B-05).
6. Recovery, rollback, maintenance and local-development documents exist and match tested behaviour.
7. `PROJECT_STATE.md` is current: verified tests with commit and run links, known bugs, security limitations, assumption outcomes, and Phase 2 entry tasks.
8. Tag `phase-1-complete` is pushed.

**Security properties Phase 1 actually proves (in a VM):** verified boot from firmware keys to root filesystem contents; immutable `/usr`; SELinux enforcing with zero boot denials; default-deny inbound network; no default credentials; signed updates and manual rollback; pinned and inventoried inputs.

**Not provided until later phases or hardware:** disk encryption and TPM binding (2); production keys (2); automatic rollback (2); application sandboxing and VM isolation (3); user/admin separation (2); intrusion detection (2); any guarantee on real firmware, real TPMs or GPUs (6).

---

## 12. Implementation handoff instructions for Claude Code

1. Work on branch `claude/aegis-os-architecture-ayxptj`. Do not open a pull request unless asked.
2. Start with P1-01: commit this blueprint as `docs/architecture/phase-1-blueprint.md`, then `PROJECT_STATE.md` and `CLAUDE.md`. Read `PROJECT_STATE.md` first in every later session.
3. Follow the task order in §8. Reach milestone M1 (first boot in CI) before adding any hardening.
4. In Claude Cloud run only the static tier. Never report a B, V or R test as passing without a CI or local run; record the run link in the state file.
5. Re-run `scripts/probe-env` at the start of a session if the environment may have changed; do not assume KVM or registry access.
6. Never commit keys, tokens or recovery secrets. Phase 1 needs no repository secrets; if a task appears to need one, stop and ask.
7. Do not weaken a control to make a test pass (no permissive SELinux, no disabled signature checks). Record the failure instead.
8. Stop and ask the owner when: G1 fails; R-02 cannot be met; A1 is refuted; any change would add a stored secret, a new external host, or a second base distribution.
9. Keep commits small; update `PROJECT_STATE.md` in the same commit as the work it describes; tag milestones.

## Verification of this plan's execution

End-to-end check after implementation: push the branch → `lint`, `build` and `vm-test` workflows green → download the JUnit and metrics artifacts → confirm every ID in §9 appears with a pass → confirm the published image verifies with `cosign verify` using the run's public key → on a local KVM machine (if available) run `just build disk test` and obtain the same results.

## Sources consulted

- bootc upstream documentation (GitHub `bootc-dev/bootc`, `docs/src`, version 1.17.4): sealed images, composefs backend, bootloaders, disk encryption, boot failure detection
- [Sealed Fedora Atomic Desktop bootable container images](https://fedoramagazine.org/sealed-atomic-desktops-test-images/?=0)
- [Privacy Guides: Fedora sealed bootable container images](https://www.privacyguides.org/news/2026/05/04/fedora-sealed-bootable-container-images-possibly-opening-the-door-to-a-fully-verified-boot-chain/)
- [Fedora 45 released](https://phoronix.com/news/Fedora-45-Released)
- [This Week in Fedora, 2–8 November 2026](https://communityblog.fedoraproject.org/this-week-in-fedora-2026-11-02/)
- [bootc-base-imagectl](https://forge.fedoraproject.org/iot/base-images/src/branch/main/bootc-base-imagectl.md)
- [RHEL 10: reproducible container builds](https://docs.redhat.com/en/documentation/Red_Hat_Enterprise_Linux/10/html/building_running_and_managing_containers/introduction-to-reproducible-container-builds)
- [RHEL-126444: non-reproducible bootc base layers](https://issues.redhat.com/browse/RHEL-126444)
- [bootc-image-builder](https://github.com/osbuild/bootc-image-builder)

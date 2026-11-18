# ADR-0004: Sealed images on the bootc composefs backend

Status: Provisional
Date: 2026-11-13 (implemented in M3, 2026-11-17)

## Context

bootc has two storage backends with no supported in-place migration. Only the composefs backend supports sealed images (signed UKI carrying the root filesystem digest, fs-verity enforced) and systemd-boot. Upstream bootc 1.17 documents both under its stability guarantees; Fedora's own sealed desktop images were test-only in spring 2026. Upstream tests the composefs backend on ext4 and XFS; btrfs (ADR-0005) is "expected to work but untested".

## Decision

Target the composefs backend with systemd-boot and a signed UKI. The decision becomes Accepted only when gate G1 passes on the pinned base: install, Secure Boot, upgrade, rollback and tamper rejection in a VM. If G1 fails, fall back to the ostree backend with shim and GRUB and mark this ADR "fallback active".

### Boot chain as built (M3)

OVMF with Secure Boot and only the build's throw-away PK/KEK/db (ADR-0007)
→ `systemd-bootx64.efi` 262, signed with the db key, as `EFI/BOOT/BOOTX64.EFI`
→ UKI built by `ukify`, signed with the db key; its command line is the arguments of
`/usr/lib/bootc/kargs.d` plus `composefs.digest=v1-sha512-12:<digest>` and the V2
fallback `composefs=<digest>`
→ initramfs `bootc-root-setup.service` mounts the composefs image with that digest,
fs-verity required
→ SELinux enforcing; `aegis-verify-cmdline.service` stops the machine if the running
command line contains anything else.

### Deviations from bootc's documented sealed-image pattern, and why

1. **The digest is computed from container storage, not from a mounted filesystem.**
   `bootc container ukify` reads a mounted root. For a directory that exists in the
   base and is changed by a derived layer, a mount shows the top layer's metadata, but
   `bootc install` keeps the lowest layer's; the digests differ and the image does not
   install (CI runs 44074603737 and 44076988380). Resetting timestamps cannot help,
   because layer diffs drop mtime-only directory changes. `scripts/build-image` uses
   `bootc container compute-composefs-digest-from-storage` on the split root
   filesystem, passes the digests to `image/build/seal-uki`, which calls `ukify` with
   the command line bootc's ukify would build, and fails the build if the finished
   image's digest differs from the sealed one.
2. **`rw` and the serial console are in `kargs.d`.** A sealed command line cannot be
   extended at installation, so the arguments `bootc install` would add must be in the
   image (run 44086672654: without `rw`, `/etc` and `/var` were read-only).
3. **A firmware-supplied command-line extension is refused by the OS.** systemd-stub
   appends `io.systemd.stub.kernel-cmdline-extra` from SMBIOS even under Secure Boot
   (it trusts measured boot to expose it). Without a TPM policy that would let the
   hypervisor or platform firmware add `enforcing=0` (run 44093307831: SELinux became
   permissive). `aegis-verify-cmdline.service`, statically enabled in the sealed root
   before `sysinit.target`, powers the machine off instead.
4. **Install-time labels are corrected** (`scripts/fix-install-labels`): the installer
   runs on a host without SELinux; each deployment's `/etc` and `/var` are labelled with
   the image's file contexts.

## Consequences

- `bootupd` and `shim` are absent from the image; systemd-boot is the only boot loader.
- `/etc` (per deployment) and `/var` (shared by deployments) are outside the sealed
  root. They are writable state on the root partition, not integrity-protected.
- The initramfs runs before `aegis-verify-cmdline.service`; a firmware-supplied argument
  is in effect until that check stops the machine. Measured boot (TPM) would close this.
- No automatic rollback on failed boot yet on this backend (no boot counting); Phase 2.
- `/var` is a mount made by the initramfs without a unit file, so systemd does not
  derive requirements from `RequiresMountsFor=/var/...`. `aegis-journal-relinquish.service`
  makes journald release `/var` at shutdown (BUG-8); other services relying on such
  requirements may need the same care.
- The image is built as root filesystem, split image and sealed image; two extra
  container-storage passes per variant compute the digests.
- Updates (V-13) and rollback (V-14) need a registry and signed images (M4); until they
  pass, G1 is open and this ADR stays Provisional.

## Verification

Done in M3 (CI, KVM, Secure Boot firmware with enrolled keys; `build` run 44300954850 on
`3a07962`, all 77 VM tests pass): B-06, V-04, V-05, V-06, V-07, boot-parameter tests;
see `PROJECT_STATE.md` section 5. Open: V-13, V-14 (M4).

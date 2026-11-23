# Graphical Live ISO (development)

Purpose: let anyone try the AEGIS OS desktop by attaching one ISO file to a VirtualBox
machine and pressing Start. User guide: `VIRTUALBOX_GUIDE.md`.

## How it is built

`make rootfs-gui` → `make live-iso` (`scripts/build-live-iso`), in CI the workflow
`.github/workflows/live-iso.yml`.

1. **Root filesystem.** `aegis-gui-rootfs`: the graphical root filesystem that
   `image/Containerfile.seal` also seals into `aegis-gui` (same locked RPMs, same AEGIS
   configuration, same SELinux policy). `scripts/build-image` stops before sealing when
   `AEGIS_ROOTFS_ONLY=1`.
2. **Live layer** (`image/Containerfile.live`, stage `root`; files in `image/rootfs-live`):
   - `aegis` (uid 1000) from a sysusers.d file: not in `wheel`, password locked; SDDM
     automatic login into Plasma (Wayland); screen locking off (the account has no
     password to unlock with); no suspend or display blanking when idle;
   - `aegis-live-admin.service`: a random root password at every boot, written only to a
     root-only agetty issue file (text consoles); `su -` accepts it;
   - a login helper that switches the first output to 1920×1080 when the virtual GPU
     offers it and starts smaller (VMSVGA without guest tools starts small);
   - removed in the live root only: `aegis-verify-cmdline.service` (no sealed command
     line exists; it would power the machine off), `aegis-journal-relinquish.service` and
     the `var.mount` ordering (both for the composefs `/var` bind mount), and the bootc
     initramfs;
   - `os-release`: `VARIANT_ID=live`, `IMAGE_ID=aegis-gui-live`.
3. **Boot files** (stage `boot`): the image's stock Fedora kernel and a new initramfs from
   dracut with `dmsquash-live` (package `dracut-live`, locked step `live`), generic
   (`--no-hostonly`) plus AHCI/PIIX, CD-ROM, ISO 9660, SquashFS, overlay and loop drivers.
   Only `/live` leaves this stage.
4. **Assembly** (`scripts/container/assemble-live-iso`, in the tools container):
   `setfiles` labels the extracted root with the image's own `file_contexts` and policy;
   `mksquashfs` (zstd level 19, 1 MiB blocks) keeps the labels and file capabilities;
   Fedora's signed `shimx64.efi`, `grubx64.efi`, `mmx64.efi` (from the builder, which is
   the same pinned base) go to `EFI/BOOT` of the ISO tree and of a small FAT image;
   `xorriso` writes an ISO 9660 / Joliet / Rock Ridge image labelled `AEGIS_LIVE` with
   that FAT image as its El Torito UEFI boot entry (`-isohybrid-gpt-basdat` also makes it
   usable from a USB stick, not tested). UEFI only: no BIOS boot.

Boot menu (`image/live/grub.cfg`): default entry after five seconds,
`root=live:CDLABEL=AEGIS_LIVE rd.live.image rd.live.overlay.overlayfs=1` plus every
argument from `/usr/lib/bootc/kargs.d` (lockdown=integrity, slab_nomerge, …, consoles).
A second entry adds `nomodeset` (firmware framebuffer) as the documented graphics
fallback; Plasma 6.8 has no X11 session to fall back to.

## Differences from the installed sealed image

See the table in `VIRTUALBOX_GUIDE.md` section 7. In short: SELinux enforcing, kernel
lockdown, kernel arguments, firewall and sysctls are the same; Secure Boot with AEGIS
keys, the sealed composefs root, the command-line check, signed updates, rollback and
persistence are absent. The SquashFS is not verified at boot (no dm-verity); a later
version could add that, together with a signed UKI, if live media become a release
artefact.

## Verification

`tests/vm/test_live_iso.py` (`make live-test`): ISO structure, then one boot in QEMU on
VirtualBox-like hardware (`VmConfig.virtualbox_like`). The only test input added to the
machine is a throw-away SSH key for root (a systemd credential in SMBIOS); the account,
automatic login and administrator password come from the ISO. VirtualBox itself is not
available on the CI runners and is therefore unverified; running it there would need
its packages from a new download host (owner decision).

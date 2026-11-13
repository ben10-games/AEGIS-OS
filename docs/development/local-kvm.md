# Building and booting AEGIS OS on a local Linux machine

These are the same steps GitHub Actions runs. They have been verified in CI; they have
**not** been verified on a developer workstation yet (see `PROJECT_STATE.md`).

Nothing here touches your real disks. The installer writes to an image file under `out/`
through a loop device, and `scripts/build-disk` refuses block devices.

## Requirements

- Linux on x86-64 with hardware virtualization (`/dev/kvm` readable and writable by you).
- `podman`, `git`, `make`, and `sudo` rights. Images are built in root's container storage
  because the installer container must be privileged.
- About 20 GiB of free disk space and access to `quay.io`.

QEMU, UEFI firmware and pytest are **not** needed on the host; they run inside the
`aegis-builder` container.

## Steps

```bash
make image
```

Builds `localhost/aegis-base` and `localhost/aegis-dev` from the base pinned in
`image/base.lock`, and runs `bootc container lint`.

```bash
make disk
```

Installs `aegis-dev` into `out/disk.raw` (12 GiB sparse file, GPT, btrfs root).

```bash
make builder
```

Builds the test container.

```bash
make vm-test
```

Boots the disk in QEMU under UEFI, waits for SSH, checks the system is healthy, powers
off, boots again. Logs land in `out/vm/logs/`, the report in `out/junit-vm.xml`.

`make m1` runs all four in order.

## Without KVM

`make vm-test` falls back to software emulation when `/dev/kvm` is not usable. Timeouts
are multiplied by ten. Expect a run to take many minutes; treat it as a last resort.

## Looking at a failure

- `out/vm/logs/test_boot-serial-boot1.log` is the serial console of the first boot.
- `out/vm/logs/boot1-journal.txt` is the guest journal, when SSH was reachable.
- `out/vm/logs/boot1-failed-units.txt` lists failed systemd units.

## Cleaning up

```bash
sudo rm -rf out
```

```bash
sudo podman rmi localhost/aegis-dev localhost/aegis-base localhost/aegis-builder
```

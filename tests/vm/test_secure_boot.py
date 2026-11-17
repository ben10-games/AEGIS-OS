"""V-04 and the authenticated command line: the development variant under Secure Boot.

The firmware is the Secure Boot build of OVMF with only this build's throw-away keys
enrolled (harness/firmware.py). Tests run in order against one virtual machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SSH_DEADLINE_S = 120
EFI_GLOBAL = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
LOADER_VENDOR = "4a67b082-0a4c-41cf-b6c7-440b29bb8c4f"


@pytest.fixture(scope="module")
def guest(vm):
    vm.start()
    vm.wait_for_ssh(SSH_DEADLINE_S)
    vm.ssh("systemctl is-system-running --wait", timeout=180, check=False)
    yield vm
    vm.ssh("systemctl poweroff", check=False)
    vm.wait_for_exit(120)


def efi_variable(guest, name: str, vendor: str) -> bytes:
    """Raw value of an EFI variable (without the 4-byte attribute header)."""
    out = guest.ssh(f"od -An -v -tx1 /sys/firmware/efi/efivars/{name}-{vendor}", check=False)
    data = bytes.fromhex("".join(out.stdout.split()))
    return data[4:]


def utf16(data: bytes) -> str:
    return data.decode("utf-16-le", errors="replace").rstrip("\x00")


def test_v04_firmware_reports_secure_boot_enabled(guest, logdir):
    """V-04: the firmware enforces Secure Boot (variable SecureBoot = 1, not setup mode)."""
    assert efi_variable(guest, "SecureBoot", EFI_GLOBAL) == b"\x01"
    assert efi_variable(guest, "SetupMode", EFI_GLOBAL) == b"\x00"
    status = guest.ssh("bootctl status --no-pager", check=False).stdout
    (logdir / "secure-boot-bootctl-status.txt").write_text(status)
    assert "Secure Boot: enabled (user)" in status


def test_v04_kernel_saw_secure_boot_and_locks_down(guest):
    """V-04: the kernel detected Secure Boot; lockdown is in integrity mode."""
    kernel = guest.ssh("journalctl -k -b --no-pager -o cat").stdout
    assert "secureboot: Secure boot enabled" in kernel
    assert "[integrity]" in guest.ssh("cat /sys/kernel/security/lockdown").stdout


def test_v04_booted_through_signed_systemd_boot_and_uki(guest):
    """The running chain is systemd-boot, then systemd-stub (a UKI), as built."""
    loader = utf16(efi_variable(guest, "LoaderInfo", LOADER_VENDOR))
    stub = utf16(efi_variable(guest, "StubInfo", LOADER_VENDOR))
    assert loader.startswith("systemd-boot "), loader
    assert stub.startswith("systemd-stub "), stub


def test_v06_command_line_is_exactly_the_sealed_one(guest):
    """The kernel runs with the command line signed into the UKI, nothing added or removed."""
    sealed = (ROOT / "out" / "sealed" / "dev-cmdline.txt").read_text().split()
    running = guest.ssh("cat /proc/cmdline").stdout.split()
    assert running == sealed


def test_v06_root_is_the_sealed_composefs_image(guest, logdir):
    """V-06: / is a read-only composefs mount of the image whose digest is on the command line."""
    mount = guest.ssh("findmnt -no SOURCE,FSTYPE,OPTIONS /").stdout.split()
    (logdir / "sealed-root-mount.txt").write_text(" ".join(mount) + "\n")
    source, fstype, options = mount[0], mount[1], mount[2]
    assert source.startswith("composefs:")
    assert fstype == "overlay"
    assert "ro" in options.split(",")
    deployed = source.split(":", 1)[1]
    assert guest.ssh(f"test -d /sysroot/state/deploy/{deployed}", check=False).returncode == 0
    result = guest.ssh("touch /usr/aegis-write-probe", check=False)
    assert result.returncode != 0 and "Read-only file system" in result.stderr


def test_v06_root_file_objects_are_protected_by_fs_verity(guest, logdir):
    """V-06: the stored object behind a root file has fs-verity on and cannot be rewritten."""
    found = guest.ssh(
        "grep -rlF 'AEGIS OS integrity canary.' /sysroot/composefs/objects | head -n 3",
        timeout=300,
    ).stdout.split()
    assert found, "the object holding /usr/share/aegis/integrity-canary was not found"
    flags = guest.ssh(f"lsattr {found[0]}").stdout
    write = guest.ssh(f"sh -c 'echo x >> {found[0]}'", check=False)
    (logdir / "fs-verity-object.txt").write_text(
        f"objects: {found}\nlsattr: {flags}\nappend attempt: rc={write.returncode} {write.stderr}"
    )
    assert "V" in flags.split()[0], f"fs-verity flag not set: {flags}"
    assert write.returncode != 0, "a root file object could be modified"


def test_v06_etc_and_var_are_outside_the_sealed_root(guest):
    """Documented boundary: /etc and /var are the machine's state and are writable.

    Also proves the sealed command-line check ran and accepted this boot."""
    # /etc belongs to the deployment; /var is shared by all deployments of the OS.
    expected = {"/etc": "/state/deploy/", "/var": "/state/os/"}
    for path, prefix in expected.items():
        source = guest.ssh(f"findmnt -no SOURCE {path}").stdout.strip()
        assert prefix in source, f"{path} comes from {source}"
    guest.ssh("touch /etc/aegis-state-probe /var/aegis-state-probe")
    guest.ssh("rm -f /etc/aegis-state-probe /var/aegis-state-probe")


def test_sealed_command_line_check_accepted_this_boot(guest):
    """aegis-verify-cmdline.service ran before sysinit.target and found nothing to object to."""
    assert guest.ssh("systemctl is-active aegis-verify-cmdline.service").stdout.strip() == "active"
    log = guest.ssh("journalctl -b -u aegis-verify-cmdline.service --no-pager -o cat").stdout
    assert "kernel command line is the sealed one" in log

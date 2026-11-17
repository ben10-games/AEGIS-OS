"""Negative tests of the sealed boot chain: V-05, V-07 and modified boot parameters.

Each test changes a private copy of a built disk the way someone with access to the
disk could, boots it with Secure Boot and this build's keys, and checks that the
change is REJECTED by the mechanism responsible, with evidence on the console or in
the system. A machine that merely fails to answer does not pass: every negative test
requires the rejection message it expects, and a control boot of an unchanged copy
shows that the same machine boots normally.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import tempfile
from pathlib import Path

import pytest
from conftest import machine
from harness.disk import Esp, private_copy, replace_bytes

KERNEL_STARTED = re.compile(r"Linux version \d")
LOGIN_PROMPT = re.compile(r"aegis login:")
# Messages of the firmware (OVMF) and systemd-boot when an image fails verification.
REJECTED = re.compile(
    r"Access Denied|Security Violation|Security violation|verification fail"
    r"|Failed to (load|start|execute)|Error (loading|starting)",
    re.IGNORECASE,
)
REJECTION_WINDOW_S = 90
SSH_DEADLINE_S = 120

UKI_DIR = "EFI/Linux/bootc"
BOOT_LOADERS = ("EFI/BOOT/BOOTX64.EFI", "EFI/systemd/systemd-bootx64.efi")
CANARY = "/usr/share/aegis/integrity-canary"


@pytest.fixture
def scratch(workdir):
    path = Path(tempfile.mkdtemp(prefix="aegis-tamper-", dir=workdir))
    yield path
    subprocess.run(["rm", "-rf", str(path)], check=False)


def uki_path(esp: Esp) -> str:
    ukis = [f for f in esp.files() if f.startswith(UKI_DIR + "/") and f.endswith(".efi")]
    assert len(ukis) == 1, f"expected one UKI on the ESP, found {ukis}"
    return ukis[0]


def unsigned(data: bytes, scratch: Path) -> bytes:
    """The same EFI binary without its Authenticode signature."""
    path = scratch / "binary.efi"
    path.write_bytes(data)
    subprocess.run(["sbattach", "--remove", str(path)], check=True, capture_output=True)
    stripped = path.read_bytes()
    assert stripped != data
    return stripped


def assert_boot_rejected(disk: Path, name: str, workdir, logdir, accel, firmware) -> str:
    """Boot a modified disk; require a rejection message and no kernel start."""
    with machine(disk, name, workdir, logdir, accel, firmware, developer_access=False) as vm:
        vm.start()
        # Judged below, with the console as evidence.
        with contextlib.suppress(AssertionError):
            vm.wait_for_serial(REJECTED, REJECTION_WINDOW_S)
        console = vm.serial_text()
        vm.kill()
    assert not KERNEL_STARTED.search(console), "the kernel started from a modified boot chain"
    match = REJECTED.search(console)
    assert match, "no verification failure was reported; console:\n" + console[-1500:]
    return match.group(0)


def test_control_unchanged_copy_boots(base_disk, scratch, workdir, logdir, accel,
                                      secure_boot_firmware):  # fmt: skip
    """Control: the unchanged release disk boots under the same firmware and keys."""
    disk = private_copy(base_disk, scratch / "disk.raw")
    with machine(disk, "integrity-control", workdir, logdir, accel, secure_boot_firmware,
                 developer_access=False) as vm:  # fmt: skip
        vm.start()
        vm.wait_for_serial(LOGIN_PROMPT, 180)
        assert KERNEL_STARTED.search(vm.serial_text())


def test_v05_unsigned_uki_is_rejected(base_disk, scratch, workdir, logdir, accel,
                                      secure_boot_firmware):  # fmt: skip
    disk = private_copy(base_disk, scratch / "disk.raw")
    esp = Esp(disk)
    uki = uki_path(esp)
    esp.write(uki, unsigned(esp.read(uki), scratch))
    message = assert_boot_rejected(disk, "integrity-unsigned-uki", workdir, logdir, accel,
                                   secure_boot_firmware)  # fmt: skip
    (logdir / "v05-unsigned-uki.txt").write_text(f"rejected with: {message}\n")


def test_v05_tampered_uki_is_rejected(base_disk, scratch, workdir, logdir, accel,
                                      secure_boot_firmware):  # fmt: skip
    """A one-byte change to the signed command line (audit=1 -> audit=0) breaks the signature."""
    disk = private_copy(base_disk, scratch / "disk.raw")
    esp = Esp(disk)
    uki = uki_path(esp)
    original = esp.read(uki)
    assert original.count(b" audit=1 ") == 1
    esp.write(uki, original.replace(b" audit=1 ", b" audit=0 "))
    message = assert_boot_rejected(disk, "integrity-tampered-uki", workdir, logdir, accel,
                                   secure_boot_firmware)  # fmt: skip
    (logdir / "v05-tampered-uki.txt").write_text(f"rejected with: {message}\n")


def test_v05_unsigned_boot_loader_is_rejected(base_disk, scratch, workdir, logdir, accel,
                                              secure_boot_firmware):  # fmt: skip
    disk = private_copy(base_disk, scratch / "disk.raw")
    esp = Esp(disk)
    for loader in BOOT_LOADERS:
        esp.write(loader, unsigned(esp.read(loader), scratch))
    message = assert_boot_rejected(disk, "integrity-unsigned-loader", workdir, logdir, accel,
                                   secure_boot_firmware)  # fmt: skip
    (logdir / "v05-unsigned-loader.txt").write_text(f"rejected with: {message}\n")


def test_v07_offline_change_to_a_root_file_is_never_returned(
    dev_disk, scratch, workdir, logdir, accel, secure_boot_firmware
):
    """V-07: change the stored bytes of a sealed root file on the disk; it must not be served."""
    disk = private_copy(dev_disk, scratch / "disk.raw")
    changed = replace_bytes(disk, b"canary line 63: the quick", b"canary line 63: the QUICK")
    assert changed >= 1, "the canary's bytes were not found on the disk"
    with machine(disk, "integrity-root-object", workdir, logdir, accel,
                 secure_boot_firmware) as vm:  # fmt: skip
        vm.start()
        vm.wait_for_ssh(SSH_DEADLINE_S)
        read = vm.ssh(f"cat {CANARY}", check=False)
        where = vm.ssh(
            "grep -rlF 'the QUICK' /sysroot 2>/dev/null | head -n 5;"
            " echo ---; grep -rlF 'canary line 63: the quick' /sysroot 2>/dev/null | head -n 5",
            timeout=600,
            check=False,
        ).stdout
        kernel = vm.ssh(
            "journalctl -k -b --no-pager -o cat | grep -iE 'verity|csum|checksum|integrity'"
            " | tail -n 20",
            check=False,
        ).stdout
        (logdir / "v07-root-object.txt").write_text(
            f"places changed on disk: {changed}\nread exit status: {read.returncode}\n"
            f"read error: {read.stderr}\nkernel messages:\n{kernel}\n"
            f"files with the changed bytes / the original bytes:\n{where}"
        )
    assert "QUICK" not in read.stdout, "modified content of a sealed file was returned"
    assert read.returncode != 0, (
        f"reading the modified file did not fail; {changed} place(s) changed on disk;"
        f" files with changed / original bytes:\n{where}"
    )
    assert "Input/output error" in read.stderr


def test_boot_loader_options_cannot_change_the_command_line(
    dev_disk, scratch, workdir, logdir, accel, secure_boot_firmware
):
    """An 'options' line added to the boot entry on the ESP is ignored under Secure Boot."""
    disk = private_copy(dev_disk, scratch / "disk.raw")
    esp = Esp(disk)
    entries = [f for f in esp.files() if f.startswith("loader/entries/") and f.endswith(".conf")]
    assert entries, "no boot entry on the ESP"
    for entry in entries:
        text = esp.read(entry).decode()
        esp.write(entry, (text.rstrip("\n") + "\noptions enforcing=0 aegis.tamper=1\n").encode())
    with machine(disk, "integrity-loader-options", workdir, logdir, accel,
                 secure_boot_firmware) as vm:  # fmt: skip
        vm.start()
        vm.wait_for_ssh(SSH_DEADLINE_S)
        command_line = vm.ssh("cat /proc/cmdline").stdout
        mode = vm.ssh("getenforce").stdout.strip()
    (logdir / "boot-parameters-loader-options.txt").write_text(
        f"command line: {command_line}\nSELinux: {mode}\n"
    )
    assert "aegis.tamper=1" not in command_line
    assert "enforcing=0" not in command_line
    assert mode == "Enforcing"


def test_firmware_supplied_command_line_extension_stops_the_machine(
    base_disk, scratch, workdir, logdir, accel, secure_boot_firmware
):
    """systemd-stub appends io.systemd.stub.kernel-cmdline-extra from the firmware's
    SMBIOS tables even under Secure Boot; run 44093307831 showed that 'enforcing=0'
    there switched SELinux to permissive. aegis-verify-cmdline.service (sealed root)
    must therefore stop the machine before sysinit.target, and say why."""
    disk = private_copy(base_disk, scratch / "disk.raw")
    extra = ("io.systemd.stub.kernel-cmdline-extra=enforcing=0 aegis.smbios=1",)
    with machine(disk, "integrity-smbios-cmdline", workdir, logdir, accel, secure_boot_firmware,
                 developer_access=False, smbios_strings=extra) as vm:  # fmt: skip
        vm.start()
        status = vm.wait_for_exit(180)
        console = vm.serial_text()
    (logdir / "boot-parameters-smbios.txt").write_text(console[-3000:])
    assert "unexpected argument: enforcing=0" in console, console[-1500:]
    assert not LOGIN_PROMPT.search(console), "the machine reached a login prompt"
    assert status == 0, "the machine did not power itself off"

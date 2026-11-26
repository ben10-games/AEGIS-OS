"""Fixtures for virtual-machine tests. These need QEMU, UEFI firmware and built disk images."""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from harness.firmware import SecureBootKeys, enrol_keys, find_secure_boot_firmware
from harness.qemu import (
    Vm,
    VmConfig,
    create_overlay,
    find_firmware,
    free_local_port,
    generate_ssh_key,
)

# Software emulation is roughly an order of magnitude slower than KVM.
TCG_TIMEOUT_SCALE = 10.0


def pytest_addoption(parser):
    parser.addoption("--disk", default="out/disk.raw", help="aegis-dev disk image")
    parser.addoption("--base-disk", default="out/disk-base.raw", help="aegis-base disk image")
    parser.addoption("--local-image", default="", help="exported qcow2 (default: out/release)")
    parser.addoption("--workdir", default="out/vm", help="directory for logs and scratch files")
    parser.addoption("--gui-disk", default="out/disk-gui.raw", help="aegis-gui disk image")
    parser.addoption(
        "--live-iso", default="out/release-live/AEGIS-OS-GUI-v2-Live.iso", help="Live ISO"
    )
    parser.addoption(
        "--sealed-variant", default="dev", help="variant whose sealed command line --disk carries"
    )
    parser.addoption(
        "--secureboot-dir",
        default="out/secureboot",
        help="public Secure Boot certificates written by the image build",
    )


@pytest.fixture(scope="session")
def accel() -> str:
    return os.environ.get("AEGIS_VM_ACCEL", "kvm")


@pytest.fixture(scope="session")
def timeout_scale(accel) -> float:
    return TCG_TIMEOUT_SCALE if accel == "tcg" else 1.0


@pytest.fixture(scope="session")
def workdir(request) -> Path:
    path = Path(request.config.getoption("--workdir")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def logdir(workdir) -> Path:
    path = workdir / "logs"
    path.mkdir(exist_ok=True)
    return path


@pytest.fixture(scope="session")
def secure_boot_firmware(request, workdir, logdir) -> tuple[Path, Path]:
    """Secure Boot firmware and a variable store with this build's keys enrolled.

    Every virtual machine gets a private copy of the store, so no test can change the
    keys another test boots with.
    """
    keys = SecureBootKeys.from_directory(
        Path(request.config.getoption("--secureboot-dir")).resolve()
    )
    code, empty_store = find_secure_boot_firmware()
    enrolled = workdir / "secureboot-vars-enrolled.fd"
    report = enrol_keys(empty_store, enrolled, keys)
    (logdir / "secureboot-enrolment.txt").write_text(
        f"firmware code: {code}\nempty variable store: {empty_store}\n{report}"
    )
    return code, enrolled


@contextlib.contextmanager
def machine(
    disk: Path,
    name: str,
    workdir: Path,
    logdir: Path,
    accel: str,
    firmware: tuple[Path, Path] | None = None,
    developer_access: bool = True,
    smbios_strings: tuple[str, ...] = (),
    graphics: bool = False,
    memory_mib: int = 4096,
):
    """A virtual machine on a fresh copy-on-write disk. Tests start and stop it themselves.

    firmware: (code, variable store) of Secure Boot firmware with enrolled keys; None
    boots with plain firmware, without Secure Boot.
    developer_access: pass an SSH key to the guest through the firmware. Tests of the
    release variant switch this off: nothing but the disk reaches such a machine.
    """
    if not disk.is_file():
        pytest.fail(f"disk image {disk} not found; build it with 'make disk'")

    # Private keys stay outside the work directory so they are never uploaded as artifacts.
    secrets = Path(tempfile.mkdtemp(prefix="aegis-vm-key-"))
    key, public_key = generate_ssh_key(secrets)

    scratch = Path(tempfile.mkdtemp(prefix="aegis-vm-", dir=workdir))
    overlay = scratch / "disk.qcow2"
    create_overlay(disk, overlay)

    code, vars_template = firmware if firmware is not None else find_firmware()
    firmware_vars = scratch / f"vars{vars_template.suffix}"
    shutil.copyfile(vars_template, firmware_vars)

    cfg = VmConfig(
        disk=overlay,
        firmware_code=code,
        firmware_vars=firmware_vars,
        ssh_port=free_local_port(),
        serial_log=logdir / f"{name}-serial.log",
        authorized_key=public_key if developer_access else "",
        accel=accel,
        qmp_socket=scratch / "qmp.sock",
        probe_port=free_local_port(),
        secure_boot=firmware is not None,
        smbios_strings=smbios_strings,
        graphics=graphics,
        memory_mib=memory_mib,
        # v3 release images: SSH only through the test credential (scripts/run-v3-tests).
        test_ssh_unit=developer_access and os.environ.get("AEGIS_TEST_SSH_UNIT") == "1",
    )
    vm = Vm(cfg, key, timeout_scale=TCG_TIMEOUT_SCALE if accel == "tcg" else 1.0)
    try:
        yield vm
    finally:
        vm.kill()
        shutil.rmtree(secrets, ignore_errors=True)
        shutil.rmtree(scratch, ignore_errors=True)


@pytest.fixture(scope="session")
def dev_disk(request) -> Path:
    return Path(request.config.getoption("--disk")).resolve()


@pytest.fixture(scope="session")
def base_disk(request) -> Path:
    return Path(request.config.getoption("--base-disk")).resolve()


@pytest.fixture(scope="module")
def vm(request, dev_disk, workdir, logdir, accel, secure_boot_firmware):
    """The development variant under Secure Boot, reachable over SSH with a key for this run."""
    name = request.module.__name__
    with machine(dev_disk, name, workdir, logdir, accel, secure_boot_firmware) as instance:
        yield instance


@pytest.fixture(scope="module")
def base_vm(request, base_disk, workdir, logdir, accel, secure_boot_firmware):
    """The release variant under Secure Boot. No key, no credential, no extra firmware
    string reaches it: it is observed through its serial console and power button only."""
    name = request.module.__name__
    with machine(
        base_disk, name, workdir, logdir, accel, secure_boot_firmware, developer_access=False
    ) as instance:
        yield instance


@pytest.fixture(scope="session")
def iso(request) -> Path:
    """The Live ISO (out/release-live/AEGIS-OS-GUI-v2-Live.iso by default)."""
    path = Path(request.config.getoption("--live-iso")).resolve()
    if not path.is_file():
        pytest.fail(f"{path} not found; build it with 'make live-iso'")
    return path

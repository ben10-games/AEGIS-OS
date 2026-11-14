"""Fixtures for virtual-machine tests. These need QEMU, UEFI firmware and built disk images."""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest
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
    parser.addoption("--workdir", default="out/vm", help="directory for logs and scratch files")


@pytest.fixture(scope="session")
def accel() -> str:
    return os.environ.get("AEGIS_VM_ACCEL", "kvm")


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


@contextlib.contextmanager
def machine(disk: Path, name: str, workdir: Path, logdir: Path, accel: str):
    """A virtual machine on a fresh copy-on-write disk. Tests start and stop it themselves."""
    if not disk.is_file():
        pytest.fail(f"disk image {disk} not found; build it with 'make disk'")

    # Private keys stay outside the work directory so they are never uploaded as artifacts.
    secrets = Path(tempfile.mkdtemp(prefix="aegis-vm-key-"))
    key, public_key = generate_ssh_key(secrets)

    scratch = Path(tempfile.mkdtemp(prefix="aegis-vm-", dir=workdir))
    overlay = scratch / "disk.qcow2"
    create_overlay(disk, overlay)

    code, vars_template = find_firmware()
    firmware_vars = scratch / f"vars{vars_template.suffix}"
    shutil.copyfile(vars_template, firmware_vars)

    cfg = VmConfig(
        disk=overlay,
        firmware_code=code,
        firmware_vars=firmware_vars,
        ssh_port=free_local_port(),
        serial_log=logdir / f"{name}-serial.log",
        authorized_key=public_key,
        accel=accel,
        qmp_socket=scratch / "qmp.sock",
        probe_port=free_local_port(),
    )
    vm = Vm(cfg, key, timeout_scale=TCG_TIMEOUT_SCALE if accel == "tcg" else 1.0)
    try:
        yield vm
    finally:
        vm.kill()
        shutil.rmtree(secrets, ignore_errors=True)
        shutil.rmtree(scratch, ignore_errors=True)


@pytest.fixture(scope="module")
def vm(request, workdir, logdir, accel):
    """The development variant: reachable over SSH with a key injected for this run."""
    disk = Path(request.config.getoption("--disk")).resolve()
    with machine(disk, request.module.__name__, workdir, logdir, accel) as instance:
        yield instance


@pytest.fixture(scope="module")
def base_vm(request, workdir, logdir, accel):
    """The release variant: no remote login, observed through the serial console only."""
    disk = Path(request.config.getoption("--base-disk")).resolve()
    with machine(disk, request.module.__name__, workdir, logdir, accel) as instance:
        yield instance

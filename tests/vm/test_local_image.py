"""The exported QCOW2 works exactly as LOCAL_VM_GUIDE.md tells a user to run it.

This test does not use the harness's own QEMU command line. It starts the published
launcher (local-vm/run-aegis-vm.sh) against the exported image, the way a person on a
Linux machine would, and checks both documented login paths: automatic root login on
the serial console and SSH with a key passed at launch. The image is opened with
--snapshot, so the file that gets published is byte-for-byte what was tested.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from harness.qemu import free_local_port, generate_ssh_key, strip_ansi

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "local-vm" / "run-aegis-vm.sh"

CONSOLE_LOGIN = re.compile(r"root@aegis")
CONSOLE_DEADLINE_S = 240
SSH_DEADLINE_S = 180
POWEROFF_DEADLINE_S = 120


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def local_image(request) -> Path:
    option = request.config.getoption("--local-image")
    if option:
        return Path(option).resolve()
    found = sorted((ROOT / "out" / "release").glob("*.qcow2"))
    if len(found) != 1:
        pytest.fail(f"expected exactly one exported image in out/release, found {found}")
    return found[0]


@pytest.fixture(scope="module")
def launched(local_image, logdir, accel):
    """The exported image, started by the published launcher."""
    secrets = Path(tempfile.mkdtemp(prefix="aegis-local-key-"))
    key, _public = generate_ssh_key(secrets)
    port = free_local_port()
    serial_log = logdir / "local-image-serial.log"
    serial_log.unlink(missing_ok=True)
    command = [
        str(LAUNCHER),
        "--image",
        str(local_image),
        "--ssh-key",
        str(key.with_suffix(".pub")),
        "--ssh-port",
        str(port),
        "--snapshot",
        "--accel",
        accel,
        "--serial",
        f"file:{serial_log}",
    ]
    with (logdir / "local-image-launcher.log").open("w") as output:
        proc = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT
        )
        try:
            yield {"proc": proc, "port": port, "key": key, "serial": serial_log}
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=30)
            shutil.rmtree(secrets, ignore_errors=True)
            # The launcher keeps a firmware variable store next to the image; it must
            # not end up in the published files.
            for leftover in local_image.parent.glob(f"{local_image.name}.uefi-vars.*"):
                leftover.unlink()


def ssh(launched, command: str, timeout: float = 60):
    return subprocess.run(
        [
            "ssh",
            "-i",
            str(launched["key"]),
            "-p",
            str(launched["port"]),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-o",
            "ConnectTimeout=5",
            "root@127.0.0.1",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_checksum_file_matches_the_exported_image(local_image):
    """SHA256SUMS, which users are told to check, describes the image being tested."""
    listed = dict(
        reversed(line.split(None, 1))
        for line in (local_image.parent / "SHA256SUMS").read_text().splitlines()
        if line.strip()
    )
    assert listed.get(local_image.name) == sha256(local_image)


def test_console_logs_in_automatically(launched, timeout_scale, record_property):
    """Documented login 1: a root shell appears on the serial console, without a password."""
    started = time.monotonic()
    deadline = started + CONSOLE_DEADLINE_S * timeout_scale
    text = ""
    while time.monotonic() < deadline:
        if launched["serial"].exists():
            text = strip_ansi(launched["serial"].read_text(errors="replace"))
            if CONSOLE_LOGIN.search(text):
                break
        assert launched["proc"].poll() is None, "the launcher exited before a login appeared"
        time.sleep(2)
    assert CONSOLE_LOGIN.search(text), "no root shell on the serial console:\n" + text[-800:]
    record_property("console_login_seconds", round(time.monotonic() - started, 1))


def test_ssh_login_with_the_key_passed_at_launch(launched, timeout_scale):
    """Documented login 2: SSH as root with the public key given to the launcher."""
    deadline = time.monotonic() + SSH_DEADLINE_S * timeout_scale
    result = None
    while time.monotonic() < deadline:
        result = ssh(launched, "true")
        if result.returncode == 0:
            break
        time.sleep(3)
    assert result is not None and result.returncode == 0, result.stderr if result else "no attempt"


def test_record_how_the_console_login_happened(launched, logdir):
    """Evidence for the guide: the login service's command line and who holds the console."""
    report = ssh(
        launched,
        "systemctl show serial-getty@ttyS0.service -p ExecStart -p DropInPaths --no-pager;"
        " echo; ps -eo label,tty,args | grep -E 'ttyS0|agetty' | grep -v grep;"
        " echo; echo -n 'AVC records since boot: ';"
        " journalctl -b --no-pager -o cat | grep -c 'avc:  denied' || true",
    )
    (logdir / "local-image-console.txt").write_text(report.stdout + report.stderr)
    assert report.returncode == 0, report.stderr
    assert "--autologin root" in report.stdout
    assert report.stdout.strip().endswith("AVC records since boot: 0"), report.stdout


def test_exported_system_is_healthy_and_enforcing(launched, timeout_scale):
    """The system a user boots is the AEGIS development image, healthy, SELinux enforcing."""
    state = ssh(launched, "systemctl is-system-running --wait", timeout=180 * timeout_scale)
    assert state.stdout.strip() == "running", state.stdout + state.stderr
    assert ssh(launched, "getenforce").stdout.strip() == "Enforcing"
    release = ssh(launched, "cat /usr/lib/os-release").stdout
    assert 'NAME="AEGIS OS"' in release
    assert "IMAGE_ID=aegis-dev" in release
    assert ssh(launched, "hostname").stdout.strip() == "aegis"
    # No password was baked in: console and SSH access exist only through the launcher.
    assert ssh(launched, "passwd -S root").stdout.split()[1] == "L"


def test_guest_powers_off_and_the_launcher_exits(launched, timeout_scale):
    """'poweroff' in the guest ends the QEMU process started by the launcher."""
    ssh(launched, "systemctl poweroff")
    assert launched["proc"].wait(timeout=POWEROFF_DEADLINE_S * timeout_scale) == 0


def test_published_image_was_not_modified_by_the_test(local_image):
    """The file that will be published is exactly the file that was booted."""
    listed = (local_image.parent / "SHA256SUMS").read_text()
    assert sha256(local_image) in listed

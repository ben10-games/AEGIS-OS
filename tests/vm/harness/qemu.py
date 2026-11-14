"""Start and stop a QEMU virtual machine booting an AEGIS OS disk image under UEFI.

The command-line construction is a pure function so it can be unit-tested on machines
that have no QEMU at all.
"""

from __future__ import annotations

import base64
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path

from harness.qmp import QmpClient

# (code, variables-template) pairs, in order of preference.
FIRMWARE_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("/usr/share/edk2/ovmf/OVMF_CODE.fd", "/usr/share/edk2/ovmf/OVMF_VARS.fd"),
    ("/usr/share/edk2/ovmf/OVMF_CODE_4M.qcow2", "/usr/share/edk2/ovmf/OVMF_VARS_4M.qcow2"),
    ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
    ("/usr/share/OVMF/OVMF_CODE.fd", "/usr/share/OVMF/OVMF_VARS.fd"),
)

ACCELERATORS = ("kvm", "tcg")

# Guest port used by firewall tests: a listener is started on it inside the guest and
# probed from outside through a forwarded host port.
PROBE_GUEST_PORT = 8080

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class HarnessError(RuntimeError):
    """The harness itself could not do its job (as opposed to a test assertion failing)."""


def find_firmware(candidates=FIRMWARE_CANDIDATES) -> tuple[Path, Path]:
    """Return the first (code, vars) UEFI firmware pair that exists on this machine."""
    for code, variables in candidates:
        if Path(code).is_file() and Path(variables).is_file():
            return Path(code), Path(variables)
    tried = ", ".join(code for code, _ in candidates)
    raise HarnessError(f"no UEFI firmware found; looked for: {tried}")


def pflash_format(path: Path) -> str:
    return "qcow2" if path.suffix == ".qcow2" else "raw"


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass(frozen=True)
class VmConfig:
    disk: Path  # qcow2 file the guest may write to
    firmware_code: Path  # read-only firmware code
    firmware_vars: Path  # writable copy of the firmware variable store
    ssh_port: int  # host-side port forwarded to guest port 22
    serial_log: Path
    authorized_key: str  # public key granted root login for this run only
    accel: str = "kvm"
    cpus: int = 2
    memory_mib: int = 4096
    qmp_socket: Path | None = None  # control socket, used to press the power button
    probe_port: int | None = None  # host-side port forwarded to guest port PROBE_GUEST_PORT


def build_qemu_command(cfg: VmConfig) -> list[str]:
    """Build the QEMU argument list for one boot of the guest."""
    if cfg.accel not in ACCELERATORS:
        raise HarnessError(f"unknown accelerator '{cfg.accel}'; expected one of {ACCELERATORS}")

    # The key reaches the guest as a systemd credential in a firmware table. Nothing is
    # written into the image or the disk. Base64 avoids QEMU's comma-separated parsing.
    credential = base64.b64encode((cfg.authorized_key.strip() + "\n").encode()).decode()

    forwards = f"hostfwd=tcp:127.0.0.1:{cfg.ssh_port}-:22"
    if cfg.probe_port is not None:
        forwards += f",hostfwd=tcp:127.0.0.1:{cfg.probe_port}-:{PROBE_GUEST_PORT}"

    command = [
        "qemu-system-x86_64",
        "-machine",
        f"q35,accel={cfg.accel}",
        "-cpu",
        "host" if cfg.accel == "kvm" else "max",
        "-smp",
        str(cfg.cpus),
        "-m",
        str(cfg.memory_mib),
        "-drive",
        f"if=pflash,unit=0,readonly=on,format={pflash_format(cfg.firmware_code)},"
        f"file={cfg.firmware_code}",
        "-drive",
        f"if=pflash,unit=1,format={pflash_format(cfg.firmware_vars)},file={cfg.firmware_vars}",
        "-drive",
        f"if=virtio,format=qcow2,file={cfg.disk}",
        "-netdev",
        f"user,id=net0,{forwards}",
        "-device",
        "virtio-net-pci,netdev=net0",
        "-device",
        "virtio-rng-pci",
        "-smbios",
        f"type=11,value=io.systemd.credential.binary:ssh.authorized_keys.root={credential}",
        "-serial",
        f"file:{cfg.serial_log}",
        "-display",
        "none",
        "-monitor",
        "none",
        "-nodefaults",
    ]
    if cfg.qmp_socket is not None:
        command += ["-qmp", f"unix:{cfg.qmp_socket},server=on,wait=off"]
    return command


def strip_ansi(text: str) -> str:
    """Remove terminal colour codes, which systemd puts around '[FAILED]' and '[  OK  ]'."""
    return _ANSI.sub("", text)


def create_overlay(base_image: Path, overlay: Path) -> None:
    """Create a copy-on-write qcow2 on top of the built disk so the build output stays pristine."""
    fmt = "qcow2" if base_image.suffix == ".qcow2" else "raw"
    subprocess.run(
        [
            "qemu-img",
            "create",
            "-q",
            "-f",
            "qcow2",
            "-F",
            fmt,
            "-b",
            str(base_image.resolve()),
            str(overlay),
        ],
        check=True,
    )


class Vm:
    """One virtual machine that can be booted several times against the same disk."""

    def __init__(self, cfg: VmConfig, ssh_key: Path, timeout_scale: float = 1.0):
        self.cfg = cfg
        self.ssh_key = ssh_key
        self.timeout_scale = timeout_scale
        self.proc: subprocess.Popen | None = None
        self.boot_count = 0
        self._qemu_log = None

    # -- lifecycle ---------------------------------------------------------------

    @property
    def serial_log(self) -> Path:
        """Serial console log of the current (or most recent) boot."""
        stem = self.cfg.serial_log
        return stem.with_name(f"{stem.stem}-boot{self.boot_count}{stem.suffix}")

    def start(self) -> None:
        if self.is_running():
            raise HarnessError("virtual machine is already running")
        self.boot_count += 1
        cfg = replace(self.cfg, serial_log=self.serial_log)
        qemu_log = self.serial_log.with_name(f"{self.serial_log.stem}-qemu.log")
        self._qemu_log = qemu_log.open("w")
        self.proc = subprocess.Popen(
            build_qemu_command(cfg),
            stdin=subprocess.DEVNULL,
            stdout=self._qemu_log,
            stderr=subprocess.STDOUT,
        )

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def wait_for_exit(self, timeout: float) -> int | None:
        """Wait for QEMU to exit by itself. Returns its exit status, or None on timeout."""
        if self.proc is None:
            raise HarnessError("virtual machine was never started")
        try:
            return self.proc.wait(timeout=timeout * self.timeout_scale)
        except subprocess.TimeoutExpired:
            return None

    def kill(self) -> None:
        if self.is_running():
            self.proc.kill()
            self.proc.wait(timeout=30)
        if self._qemu_log is not None:
            self._qemu_log.close()
            self._qemu_log = None

    # -- console and power button (work without any login) ------------------------

    def serial_text(self) -> str:
        """Serial console output of the current boot, without colour codes."""
        if not self.serial_log.exists():
            return ""
        return strip_ansi(self.serial_log.read_text(errors="replace"))

    def wait_for_serial(self, pattern: re.Pattern, timeout: float) -> float:
        """Wait until the serial console matches a pattern. Returns the seconds it took."""
        started = time.monotonic()
        deadline = started + timeout * self.timeout_scale
        while time.monotonic() < deadline:
            if pattern.search(self.serial_text()):
                return time.monotonic() - started
            if not self.is_running():
                raise AssertionError(
                    f"QEMU exited with status {self.proc.returncode} while waiting for "
                    f"'{pattern.pattern}' on the serial console; see {self.serial_log}"
                )
            time.sleep(1)
        raise AssertionError(
            f"'{pattern.pattern}' did not appear on the serial console within "
            f"{timeout * self.timeout_scale:.0f}s; see {self.serial_log}"
        )

    def press_power_button(self) -> None:
        """Send the ACPI power-button event, as a person pressing the button would."""
        if self.cfg.qmp_socket is None:
            raise HarnessError("this virtual machine was started without a control socket")
        with QmpClient(self.cfg.qmp_socket) as qmp:
            qmp.command("system_powerdown")

    # -- guest access ------------------------------------------------------------

    def _ssh_command(self, command: str, connect_timeout: int = 5) -> list[str]:
        return [
            "ssh",
            "-i",
            str(self.ssh_key),
            "-p",
            str(self.cfg.ssh_port),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-o",
            f"ConnectTimeout={connect_timeout}",
            "root@127.0.0.1",
            command,
        ]

    def ssh(self, command: str, timeout: float = 60, check: bool = True):
        """Run a command in the guest as root and return the completed process."""
        result = subprocess.run(
            self._ssh_command(command),
            capture_output=True,
            text=True,
            timeout=timeout * self.timeout_scale,
            check=False,
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"guest command failed ({result.returncode}): {command}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result

    def wait_for_ssh(self, timeout: float) -> float:
        """Wait until a root shell is reachable. Returns the seconds it took."""
        started = time.monotonic()
        deadline = started + timeout * self.timeout_scale
        last_error = ""
        while time.monotonic() < deadline:
            if not self.is_running():
                raise AssertionError(
                    f"QEMU exited with status {self.proc.returncode} before SSH came up; "
                    f"see {self.serial_log}"
                )
            try:
                result = subprocess.run(
                    self._ssh_command("true"),
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                last_error = "ssh attempt timed out"
            else:
                if result.returncode == 0:
                    return time.monotonic() - started
                last_error = result.stderr.strip()
            time.sleep(2)
        raise AssertionError(
            f"SSH not reachable within {timeout * self.timeout_scale:.0f}s "
            f"(last error: {last_error or 'none'}); see {self.serial_log}"
        )


def generate_ssh_key(directory: Path) -> tuple[Path, str]:
    """Create a throw-away ed25519 key pair for one test session."""
    if shutil.which("ssh-keygen") is None:
        raise HarnessError("ssh-keygen not found")
    key = directory / "id_ed25519"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "aegis-vm-test", "-f", str(key)],
        check=True,
    )
    return key, key.with_suffix(".pub").read_text().strip()

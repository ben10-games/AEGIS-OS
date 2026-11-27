"""AEGIS OS v3 (M8): the persistent VirtualBox disk, booted the way a user would use it.

The exported VDI file itself (out/release-v3/*.vdi, through a copy-on-write overlay, so
the published file is not changed) is booted in QEMU on VirtualBox-like hardware: the
disk on a SATA controller, i440FX, OVMF without Secure Boot keys (VirtualBox's default),
standard VGA (QEMU's VMware SVGA II does not show the desktop: live-iso run 45189500261),
e1000, PS/2 keyboard, USB tablet, HDA, 4 GiB, 2 CPUs. This is QEMU, not VirtualBox.

The only test input is SSH access for the harness: a throw-away key and a one-boot unit
that opens SSH, both as firmware credentials (VmConfig.test_ssh_unit); the image itself
has the SSH server disabled. Everything else is done like a person would: the first
account is created by typing into AEGIS Setup, the user logs in by typing the password at
the login screen, and after a complete power-off the machine is started again.
"""

from __future__ import annotations

import base64
import contextlib
import secrets
import shutil
import subprocess
import tempfile
import time
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

ROOT = Path(__file__).resolve().parents[2]
USER = "tester"
FULL_NAME = "Aegis Tester"
PASSWORD = "aegis" + secrets.token_hex(6)  # lower case and digits: typed through QMP
TOKEN = secrets.token_hex(8)

REQUEST = """
import socket, sys
s = socket.socket(socket.AF_UNIX)
s.connect("/run/aegis/provision.sock")
s.sendall(b'{"full_name": "Second", "user_name": "second", "password": "abcdefghij"}\\n')
print(s.recv(4096).decode().strip())
"""


@pytest.fixture(scope="module")
def vdi() -> Path:
    found = sorted((ROOT / "out/release-v3").glob("*.vdi"))
    if len(found) != 1:
        pytest.fail(f"expected one VDI in out/release-v3, found {found}")
    return found[0]


@contextlib.contextmanager
def vdi_machine(vdi: Path, workdir: Path, logdir: Path, accel: str, label: str, cpus: int = 2):
    """The VDI behind a copy-on-write overlay, on VirtualBox-like hardware."""
    secrets_dir = Path(tempfile.mkdtemp(prefix="aegis-v3-key-"))
    key, public_key = generate_ssh_key(secrets_dir)
    scratch = Path(tempfile.mkdtemp(prefix="aegis-v3-", dir=workdir))
    overlay = scratch / "disk.qcow2"
    create_overlay(vdi, overlay)
    code, vars_template = find_firmware()
    firmware_vars = scratch / f"vars{vars_template.suffix}"
    shutil.copyfile(vars_template, firmware_vars)
    cfg = VmConfig(
        disk=overlay,
        firmware_code=code,
        firmware_vars=firmware_vars,
        ssh_port=free_local_port(),
        serial_log=logdir / f"{label}-serial.log",
        authorized_key=public_key,
        accel=accel,
        cpus=cpus,
        memory_mib=4096,
        qmp_socket=scratch / "qmp.sock",
        graphics=True,
        virtualbox_like=True,
        vbox_display="VGA",
        vbox_disk="hdd",
        console_diagnostics=False,
        test_ssh_unit=True,
    )
    machine = Vm(cfg, key, timeout_scale=10.0 if accel == "tcg" else 1.0)
    try:
        yield machine
    finally:
        machine.kill()
        shutil.rmtree(secrets_dir, ignore_errors=True)
        shutil.rmtree(scratch, ignore_errors=True)


@pytest.fixture(scope="module")
def vm(vdi, workdir, logdir, accel):
    with vdi_machine(vdi, workdir, logdir, accel, "v3") as machine:
        yield machine


def log(logdir: Path, name: str, text: str) -> None:
    with (logdir / f"v3-{name}.txt").open("a") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


def shot(vm, logdir: Path, name: str) -> Path:
    return vm.screenshot(logdir / f"v3-{name}.ppm", fmt="ppm")


def wait_for(vm, command: str, deadline_s: float, what: str) -> float:
    started = time.monotonic()
    while time.monotonic() - started < deadline_s * vm.timeout_scale:
        assert vm.is_running(), f"the VM stopped while waiting for {what}"
        if vm.ssh(command, check=False, timeout=30).returncode == 0:
            return time.monotonic() - started
        time.sleep(3)
    raise AssertionError(f"{what} did not happen within {deadline_s} s")


def as_user(vm, command: str, check: bool = True, timeout: float = 60):
    uid = vm.ssh(f"id -u {USER}").stdout.strip()
    environment = (
        f"XDG_RUNTIME_DIR=/run/user/{uid} DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus "
        "WAYLAND_DISPLAY=wayland-0 QT_QPA_PLATFORM=wayland"
    )
    return vm.ssh(
        f"runuser -u {USER} -- env {environment} sh -c '{command}'", check=check, timeout=timeout
    )


def boot(vm, logdir: Path, label: str) -> None:
    started = time.monotonic()
    vm.start()
    seconds = vm.wait_for_ssh(300)
    log(
        logdir,
        "timings",
        f"{label}: power-on to SSH {seconds:.1f} s ({time.monotonic() - started:.1f} s)",
    )


def log_in_at_greeter(vm, logdir: Path, label: str, keep_tour: bool = False) -> float:
    """Type the password at SDDM's login screen, as a person would. The Welcome tour
    (M11) starts after a login until it is finished; suites that test other things close
    it (KEEP_TOUR leaves it running, for tests/vm/test_v3_welcome.py)."""
    wait_for(vm, "pgrep -f sddm-greeter", 180, "the login screen")
    time.sleep(10)
    shot(vm, logdir, f"greeter-{label}")
    started = time.monotonic()
    vm.type_text(PASSWORD + "\n")
    wait_for(
        vm,
        f"pgrep -u {USER} -x plasmashell && pgrep -u {USER} -x kwin_wayland",
        240,
        "the desktop after logging in",
    )
    seconds = time.monotonic() - started
    log(logdir, "timings", f"{label}: password typed to desktop processes {seconds:.1f} s")
    if not keep_tour:
        for _ in range(30):
            if vm.ssh(f"pkill -u {USER} -x aegis-welcome", check=False).returncode == 0:
                break
            time.sleep(1)
    return seconds


# --- the file -------------------------------------------------------------------------


def test_vdi_file(vdi, logdir):
    listed = (vdi.parent / "SHA256SUMS").read_text()
    digest = subprocess.run(["sha256sum", str(vdi)], capture_output=True, text=True, check=True)
    assert digest.stdout.split()[0] in listed
    info = subprocess.run(
        ["qemu-img", "info", "--output=human", str(vdi)], capture_output=True, text=True
    ).stdout
    log(logdir, "vdi", info)
    assert "file format: vdi" in info
    assert "virtual size: 64 GiB" in info
    assert not list(vdi.parent.rglob("*.key")), "a private key file is in the release"


# --- first boot: no account; AEGIS Setup ------------------------------------------------


def test_first_boot_starts_aegis_setup(vm, logdir):
    boot(vm, logdir, "first boot")
    wait_for(vm, "pgrep -u aegis-setup -x aegis-setup", 240, "AEGIS Setup")
    users = vm.ssh("awk -F: '$3 >= 1000 && $3 < 60000 {print $1}' /etc/passwd").stdout.strip()
    assert not users, f"accounts exist before setup: {users}"
    assert vm.ssh("passwd -S root").stdout.split()[1] == "L"
    assert vm.ssh("test -e /var/lib/aegis/provisioned", check=False).returncode != 0
    ssh_state = vm.ssh("systemctl is-enabled sshd.service", check=False).stdout.strip()
    permanent = vm.ssh("firewall-cmd --permanent --zone=aegis --list-services").stdout
    log(logdir, "release", f"sshd enabled: {ssh_state}; permanent firewall services: {permanent}")
    assert ssh_state == "disabled", "the release image starts the SSH server by itself"
    assert "ssh" not in permanent.split()
    time.sleep(8)
    shot(vm, logdir, "setup")


def test_account_is_created_by_typing_into_setup(vm, logdir):
    vm.type_text(FULL_NAME)
    vm.send_keys("tab", "ctrl-a")
    vm.type_text(USER)
    vm.send_keys("tab")
    vm.type_text(PASSWORD)
    vm.send_keys("tab")
    vm.type_text(PASSWORD)
    time.sleep(1)
    shot(vm, logdir, "setup-filled")
    vm.send_keys("ret")
    wait_for(vm, "test -e /var/lib/aegis/provisioned", 60, "the account to be created")
    entry = vm.ssh(f"getent passwd {USER}").stdout.strip()
    log(logdir, "account", entry)
    assert f":{FULL_NAME}:" in entry
    assert int(entry.split(":")[2]) >= 1000
    assert "wheel" in vm.ssh(f"id -nG {USER}").stdout.split()
    assert vm.ssh(f"passwd -S {USER}").stdout.split()[1] == "P"
    assert vm.ssh("passwd -S root").stdout.split()[1] == "L"
    assert vm.ssh("test -e /etc/sddm.conf.d/90-aegis-firstboot.conf", check=False).returncode
    script = base64.b64encode(REQUEST.encode()).decode()
    second = vm.ssh(f"echo {script} | base64 -d | python3 -", check=False).stdout
    log(logdir, "account", f"second request: {second}")
    assert '"ok": false' in second, f"a second account request was not refused: {second}"
    assert vm.ssh("getent passwd second", check=False).returncode != 0
    journal = vm.ssh("journalctl -b -o cat -u 'aegis-provision@*'").stdout
    assert PASSWORD not in journal, "the password appears in the journal"


def test_login_screen_and_desktop(vm, logdir, record_property):
    seconds = log_in_at_greeter(vm, logdir, "first")
    record_property("seconds_password_to_desktop", round(seconds, 1))
    session = vm.ssh(
        f"loginctl list-sessions --no-legend | awk '$3 == \"{USER}\" {{print $1}}'"
    ).stdout.split()[0]
    assert vm.ssh(f"loginctl show-session {session} -p Type --value").stdout.strip() == "wayland"
    sudo = vm.ssh(
        f"printf '%s\\n' '{PASSWORD}' | runuser -u {USER} -- sudo -S -k id -u", check=False
    )
    assert sudo.stdout.strip().endswith("0"), sudo.stdout + sudo.stderr
    time.sleep(15)
    shot(vm, logdir, "desktop")


def test_sealed_root_selinux_and_no_failures(vm, logdir):
    assert vm.ssh("getenforce").stdout.strip() == "Enforcing"
    assert vm.ssh("findmnt -no SOURCE /").stdout.startswith("composefs")
    assert vm.ssh("systemctl is-active aegis-verify-cmdline.service").stdout.strip() == "active"
    status = vm.ssh("bootc status --format=humanreadable 2>&1 | head -n 20", check=False).stdout
    denials = vm.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    failed = vm.ssh("systemctl --failed --no-legend --plain").stdout.strip()
    log(logdir, "system", f"{status}\nfailed: {failed or 'none'}\ndenials:\n{denials or 'none'}")
    assert not denials.strip(), denials[:3000]
    assert not failed, failed


def test_files_and_settings_survive_a_complete_power_off(vm, logdir):
    """Write a file, change the colour scheme, the glass profile and the wallpaper; power
    off; start again; log in at the login screen; everything is still there."""
    home = vm.ssh(f"getent passwd {USER} | cut -d: -f6").stdout.strip()
    as_user(vm, f"mkdir -p {home}/Documents && echo {TOKEN} > {home}/Documents/aegis-persist.txt")
    # The colour scheme the way System Settings sets it (KColorSchemeManager), then a
    # wallpaper change: AEGIS tints the accent from the wallpaper, which re-applies the
    # scheme, and the user's choice must survive that too.
    # Inside the session (systemd-run --user gets the environment Plasma exported), like
    # an application started from the desktop: from runuser's hand-made environment the
    # tool aborts (v3 run 45825312270), as kscreen-doctor did (live-iso run 45601312768).
    as_user(vm, "systemd-run --user --wait --collect --quiet plasma-apply-colorscheme AEGISLight")
    as_user(vm, "/usr/libexec/aegis/glass-profile apply full")
    as_user(
        vm,
        "plasma-apply-wallpaperimage /usr/share/wallpapers/AEGIS/contents/images/1920x1080.png",
        check=False,
    )
    time.sleep(5)
    before = as_user(
        vm, "kreadconfig6 --file kdeglobals --group General --key ColorScheme", check=False
    ).stdout.strip()
    log(logdir, "persistence", f"colour scheme before power-off: {before}")
    vm.ssh("sync")
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0, "the VM did not power off cleanly"

    boot(vm, logdir, "second boot")
    assert vm.ssh("test -e /var/lib/aegis/provisioned").returncode == 0
    assert vm.ssh("pgrep -u aegis-setup -x aegis-setup", check=False).returncode != 0
    log_in_at_greeter(vm, logdir, "second")
    kept = {
        "file": vm.ssh(f"cat {home}/Documents/aegis-persist.txt", check=False).stdout.strip(),
        "colour scheme": as_user(
            vm, "kreadconfig6 --file kdeglobals --group General --key ColorScheme"
        ).stdout.strip(),
        "glass profile": as_user(
            vm, "kreadconfig6 --file aegis-glassrc --group General --key Profile"
        ).stdout.strip(),
        "wallpaper": vm.ssh(
            f"grep -h '^Image=' {home}/.config/plasma-org.kde.plasma.desktop-appletsrc || true"
        ).stdout.strip(),
        "account": vm.ssh(f"getent passwd {USER}").stdout.strip(),
    }
    log(logdir, "persistence", "\n".join(f"{k}: {v}" for k, v in kept.items()))
    assert kept["file"] == TOKEN
    assert kept["colour scheme"] == "AEGISLight"
    assert kept["glass profile"] == "full"
    assert "1920x1080.png" in kept["wallpaper"] or "AEGIS" in kept["wallpaper"]
    assert f":{FULL_NAME}:" in kept["account"]
    time.sleep(10)
    shot(vm, logdir, "desktop-after-reboot")


def test_clean_power_off(vm):
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0

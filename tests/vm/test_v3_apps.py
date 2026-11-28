"""AEGIS OS v3 (M9): applications installed by the user persist on the VDI.

The exported VDI (through a copy-on-write overlay) on the same VirtualBox-like hardware
as tests/vm/test_v3_vdi.py, with 4 CPUs. The account is created through the setup
socket (typing into AEGIS Setup is tested in test_v3_vdi.py); the user logs in by
typing the password at the login screen. Google Chrome is installed from Flathub into
the user's own installation, started, the machine is powered off completely, started
again, and Chrome must still be installed and start.

Needs the internet: Flathub (dl.flathub.org and its download network) and Google's
download server (the Flathub package fetches Chrome at install time), the same hosts
as the Live ISO's Flatpak suite. scripts/run-v3-tests runs it in its own container with
network access; everything else stays offline. This is QEMU, not VirtualBox.
"""

from __future__ import annotations

import base64
import json
import re
import time

import pytest
from test_v3_vdi import (
    FULL_NAME,
    PASSWORD,
    USER,
    as_user,
    boot,
    log,
    log_in_at_greeter,
    shot,
    vdi,  # noqa: F401  (fixture)
    vdi_machine,
    wait_for,
)

CHROME = "com.google.Chrome"
INSTALL_TIMEOUT_S = 1200

WINDOWS = """
for (const w of workspace.windowList()) {
    if (w.normalWindow || w.dialog) {
        console.info("AEGIS-WINDOW " + w.resourceClass + " " + w.caption);
    }
}
"""

CREATE = r"""
import socket, sys
s = socket.socket(socket.AF_UNIX)
s.connect("/run/aegis/provision.sock")
s.sendall(sys.stdin.buffer.read().rstrip(b"\n") + b"\n")  # the helper reads one line
print(s.recv(4096).decode().strip())
"""


@pytest.fixture(scope="module")
def vm(vdi, workdir, logdir, accel):  # noqa: F811
    with vdi_machine(vdi, workdir, logdir, accel, "v3-apps", cpus=4) as machine:
        yield machine


def space(vm) -> str:
    return vm.ssh("df -h --output=target,size,used,avail / /var; free -m", check=False).stdout


def chrome_starts(vm, logdir, label: str) -> None:
    as_user(
        vm,
        f"systemd-run --user --collect --unit=aegis-test-chrome-{label} "
        f"flatpak run {CHROME} --no-first-run --no-default-browser-check about:blank",
    )
    seconds = wait_for(vm, f"pgrep -u {USER} -f /app/extra/chrome", 120, "Chrome to start")
    time.sleep(20)
    processes = vm.ssh(f"pgrep -u {USER} -fa /app/extra/chrome | head -n 3", check=False).stdout
    log(logdir, "apps", f"{label}: Chrome process after {seconds:.1f} s\n{processes}")
    assert processes.strip(), "Chrome exited"
    shot(vm, logdir, f"chrome-{label}")
    # pam_kwallet (package pam-kwallet) opened the wallet at the login, so Chrome's first
    # use of the system's secret storage must not open KDE's wallet setup assistant (v3
    # run 46015720076).
    from test_v3_desktop import kwin  # here: test_v3_desktop imports this module

    windows = kwin(vm, WINDOWS, "AEGIS-WINDOW")
    log(logdir, "apps", f"{label}: windows " + "; ".join(" ".join(w) for w in windows))
    wallet_windows = [w for w in windows if re.search("kwallet|ksecret", w[0], re.I)]
    assert not wallet_windows, f"a KDE Wallet window opened with Chrome: {wallet_windows}"
    as_user(vm, f"systemctl --user stop aegis-test-chrome-{label}.service", check=False)


def test_account_and_desktop(vm, logdir):
    boot(vm, logdir, "apps first boot")
    wait_for(vm, "pgrep -u aegis-setup -x aegis-setup", 240, "AEGIS Setup")
    request = json.dumps(
        {"full_name": FULL_NAME, "user_name": USER, "password": PASSWORD, "administrator": True}
    )
    script = base64.b64encode(CREATE.encode()).decode()
    payload = base64.b64encode(request.encode()).decode()
    reply = vm.ssh(
        f"echo {payload} | base64 -d | runuser -u aegis-setup -- "
        f'python3 -c "$(echo {script} | base64 -d)"'
    ).stdout
    assert '"ok": true' in reply, reply
    log_in_at_greeter(vm, logdir, "apps-first")


def test_flathub_is_a_user_remote_only(vm, logdir):
    wait_for(
        vm,
        f"runuser -u {USER} -- flatpak remotes --user --columns=name | grep -qx flathub",
        120,
        "the per-user Flathub remote",
    )
    remotes = as_user(vm, "flatpak remotes --user --columns=name,url").stdout
    system = vm.ssh("flatpak remotes --system --columns=name").stdout.strip()
    log(logdir, "apps", f"user remotes:\n{remotes}system remotes: {system or 'none'}")
    assert re.search(r"^flathub\s+https://dl\.flathub\.org/repo/", remotes, re.M), remotes
    assert not system, "a system-wide remote would need administrator rights"


def test_chrome_installs_into_the_persistent_home(vm, logdir, record_property):
    log(logdir, "apps", f"space before installing Chrome:\n{space(vm)}")
    started = time.monotonic()
    result = as_user(
        vm,
        f"flatpak install --user --noninteractive -y flathub {CHROME} 2>&1",
        check=False,
        timeout=INSTALL_TIMEOUT_S,
    )
    seconds = time.monotonic() - started
    record_property("seconds_to_install_chrome", round(seconds, 1))
    log(
        logdir,
        "apps",
        f"flatpak install --user {CHROME}: exit {result.returncode} after {seconds:.0f} s\n"
        + "\n".join(result.stdout.splitlines()[-15:]),
    )
    log(logdir, "apps", f"space after installing Chrome:\n{space(vm)}")
    assert result.returncode == 0, result.stdout[-3000:]
    assert "Installation: user" in as_user(vm, f"flatpak info --user {CHROME}").stdout
    where = vm.ssh(
        f"findmnt -no FSTYPE,SOURCE --target /var/home/{USER}/.local/share/flatpak"
    ).stdout.strip()
    log(logdir, "apps", f"Flatpak data on: {where}")
    assert where.startswith("btrfs"), f"Flatpak data is on {where}, not the persistent disk"


def test_chrome_starts(vm, logdir):
    chrome_starts(vm, logdir, "before")


def test_chrome_survives_a_complete_power_off(vm, logdir):
    vm.ssh("sync")
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0, "the VM did not power off cleanly"
    boot(vm, logdir, "apps second boot")
    log_in_at_greeter(vm, logdir, "apps-second")
    listed = as_user(vm, "flatpak list --user --app --columns=application").stdout
    log(logdir, "apps", f"after the power-off, user applications:\n{listed}")
    assert CHROME in listed.split()
    chrome_starts(vm, logdir, "after")


def test_selinux_enforcing_without_denials(vm, logdir):
    assert vm.ssh("getenforce").stdout.strip() == "Enforcing"
    denials = vm.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    log(logdir, "apps-denials", denials or "none")
    assert not denials.strip(), denials[:3000]
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0

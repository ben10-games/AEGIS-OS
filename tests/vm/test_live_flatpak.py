"""Live ISO: Flatpak and Flathub for the unprivileged live account, with Google Chrome.

Owner request after the first VirtualBox boot: Flatpak in the Live ISO, Flathub as an
application source, user installations by the account 'aegis' (no administrator
rights), and Google Chrome (com.google.Chrome) installed and started.

Unlike tests/vm/test_live_iso.py this module needs the internet: Flathub
(dl.flathub.org and its download network) and, for Chrome, Google's download server
(the Flathub package fetches Chrome itself at install time). It is run in its own
container with network access by scripts/run-live-tests; everything else stays offline.

One boot on the same VirtualBox-like hardware with 4 GiB of memory. Everything the
test installs is written to the RAM overlay of the live system and is lost at
power-off; this module does not test persistence (a separate milestone).
"""

from __future__ import annotations

import re
import time

import pytest
from test_live_iso import USER, as_user, booted, log, shot, wait_for

CHROME = "com.google.Chrome"
INSTALL_TIMEOUT_S = 1200


@pytest.fixture(scope="module")
def vm(iso, workdir, logdir, accel):
    with booted(iso, workdir, logdir, accel, "VGA", "live-flatpak") as machine:
        wait_for(
            machine,
            f"pgrep -u {USER} -x plasmashell && pgrep -u {USER} -x kwin_wayland",
            300,
            "a Plasma Wayland session for the live account",
        )
        yield machine


def space(vm) -> str:
    """Free space of the root overlay and of /run, which holds the overlay, and memory."""
    return vm.ssh(
        "df -h --output=target,size,used,avail / /run; free -m; swapon --show", check=False
    ).stdout


def test_flatpak_with_flathub_for_the_live_account_only(vm, logdir):
    version = vm.ssh("flatpak --version").stdout.strip()
    user_remotes = as_user(vm, "flatpak remotes --user --columns=name,url").stdout
    system_remotes = vm.ssh("flatpak remotes --system --columns=name").stdout.strip()
    unit = as_user(vm, "systemctl --user is-active aegis-flathub-user-remote.service", False)
    origin = vm.ssh(
        "systemctl list-unit-files 'flatpak*' --no-legend; "
        "grep -rls registry.fedoraproject.org /etc/flatpak /var/lib/flatpak/repo/config "
        "/usr/share/flatpak /usr/lib/flatpak 2>/dev/null",
        check=False,
    ).stdout
    log(
        logdir,
        "flatpak",
        f"{version}\nuser remotes:\n{user_remotes}\nsystem remotes: {system_remotes or 'none'}\n"
        f"remote unit: {unit.stdout.strip()}\nflatpak units and remote files:\n{origin}",
    )
    assert re.search(r"^flathub\s+https://dl\.flathub\.org/repo/", user_remotes, re.M), user_remotes
    assert not system_remotes, "a system-wide remote would need administrator rights"
    assert "wheel" not in vm.ssh(f"id -nG {USER}").stdout.split()


def test_chrome_installs_into_the_user_installation(vm, logdir, record_property):
    log(logdir, "flatpak", f"space before installing Chrome:\n{space(vm)}")
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
        "flatpak",
        f"flatpak install --user {CHROME}: exit {result.returncode} after {seconds:.0f} s\n"
        + "\n".join(result.stdout.splitlines()[-25:]),
    )
    log(logdir, "flatpak", f"space after installing Chrome:\n{space(vm)}")
    usage = vm.ssh(
        f"du -sh /var/home/{USER}/.local/share/flatpak /run/overlayfs 2>/dev/null", check=False
    ).stdout
    log(logdir, "flatpak", f"disk use:\n{usage}")
    assert result.returncode == 0, result.stdout[-3000:]
    info = as_user(vm, f"flatpak info --user {CHROME}").stdout
    log(logdir, "flatpak", "\n".join(info.splitlines()[:12]))
    assert "Installation: user" in info, info
    assert not vm.ssh("flatpak list --system --columns=application").stdout.strip()
    where = vm.ssh(
        f"findmnt -no FSTYPE --target /var/home/{USER}/.local/share/flatpak"
    ).stdout.strip()
    assert where == "overlay", f"Flatpak data is on {where}, expected the live RAM overlay"
    desktop = f"/var/home/{USER}/.local/share/flatpak/exports/share/applications/{CHROME}.desktop"
    assert vm.ssh(f"test -f {desktop}", check=False).returncode == 0, "no launcher entry"


def test_chrome_starts_in_the_desktop_session(vm, logdir):
    as_user(
        vm,
        "systemd-run --user --collect --unit=aegis-test-chrome "
        f"flatpak run {CHROME} --no-first-run --no-default-browser-check about:blank",
    )
    seconds = wait_for(vm, f"pgrep -u {USER} -f /app/extra/chrome", 120, "Chrome to start")
    time.sleep(20)
    processes = vm.ssh(f"pgrep -u {USER} -fa /app/extra/chrome | head -n 5", check=False).stdout
    window = as_user(vm, "systemctl --user is-active aegis-test-chrome.service", False)
    log(
        logdir,
        "flatpak",
        f"Chrome process after {seconds:.1f} s; unit {window.stdout.strip()}\n{processes}",
    )
    assert processes.strip(), "Chrome exited"
    shot(vm, logdir, "chrome")
    log(logdir, "flatpak", f"space with Chrome running:\n{space(vm)}")


def test_selinux_enforcing_without_denials_after_flatpak(vm, logdir):
    assert vm.ssh("getenforce").stdout.strip() == "Enforcing"
    denials = vm.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    failed = vm.ssh("systemctl --failed --no-legend --plain").stdout.strip()
    log(logdir, "flatpak-denials", denials or "none")
    log(logdir, "flatpak", f"failed units: {failed or 'none'}")
    assert not denials.strip(), denials[:3000]
    assert not failed, failed

"""AEGIS OS v3 (M12): the AEGIS App Center, used as a person would, on the persistent VDI.

The exported VDI on VirtualBox-like hardware with 4 CPUs (QEMU, not VirtualBox), with
the internet (Flathub; Chrome's package downloads from Google). The App Center is driven
through its accessible controls (AT-SPI) and the virtual keyboard, and every result is
checked against Flatpak itself:

- the Flathub catalogue loads; searching finds Google Chrome and Firefox;
- an application page shows the publisher state with its explanation (verified does not
  mean safe) and the permissions in plain words;
- Install shows progress and installs into the user's own installation (no system-wide
  install, no administrator password); Open starts the app;
- an available update is announced by the daily check without being applied, then
  installed from the Updates tab when the user asks;
- Remove uninstalls; with Flathub unreachable the error says so plainly;
- an application installed with the App Center is still there after a power-off.
"""

from __future__ import annotations

import base64
import json
import time

import pytest
from test_v3_apps import CREATE
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
from test_v3_welcome import ATSPI

CHROME = "com.google.Chrome"
APP_ATSPI = ATSPI.replace(
    '("aegis-welcome", "Welcome to AEGIS")', '("aegis-appcenter", "AEGIS App Center")'
)
assert APP_ATSPI != ATSPI, "the AT-SPI helper no longer names the tour's applications"
INSTALL_TIMEOUT_S = 1200


@pytest.fixture(scope="module")
def vm(vdi, workdir, logdir, accel):  # noqa: F811
    with vdi_machine(vdi, workdir, logdir, accel, "v3-appcenter", cpus=4) as machine:
        yield machine


def in_session(vm, command: str, check: bool = True, timeout: float = 60):
    return as_user(
        vm, f"systemd-run --user --wait --pipe --quiet {command}", check=check, timeout=timeout
    )


def atspi(vm, *arguments: str, check: bool = True):
    script = base64.b64encode(APP_ATSPI.encode()).decode()
    quoted = " ".join(json.dumps(a) for a in arguments)
    vm.ssh(f"echo {script} | base64 -d > /tmp/aegis-ac.py && chmod 0644 /tmp/aegis-ac.py")
    return in_session(vm, f"python3 /tmp/aegis-ac.py {quoted}", check=check)


def dump(vm) -> str:
    return atspi(vm, "dump", check=False).stdout


def press(vm, name: str, deadline_s: float = 20) -> None:
    started = time.monotonic()
    while time.monotonic() - started < deadline_s:
        if atspi(vm, "press", name, check=False).returncode == 0:
            time.sleep(2)
            return
        time.sleep(1)
    raise AssertionError(f"no control named {name!r}; showing:\n{dump(vm)[-3000:]}")


def wait_text(vm, text: str, deadline_s: float, what: str) -> float:
    started = time.monotonic()
    while time.monotonic() - started < deadline_s:
        if text in dump(vm):
            return time.monotonic() - started
        time.sleep(3)
    raise AssertionError(f"{what}: {text!r} not shown; showing:\n{dump(vm)[-3000:]}")


def user_apps(vm) -> list[str]:
    return as_user(vm, "flatpak list --user --app --columns=application", False).stdout.split()


def start_app_center(vm) -> None:
    vm.ssh(f"pkill -u {USER} -x aegis-appcenter", check=False)
    time.sleep(1)
    as_user(
        vm,
        "systemd-run --user --collect --quiet "
        "--setenv=QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 aegis-appcenter",
        check=False,
    )
    wait_for(vm, f"pgrep -u {USER} -x aegis-appcenter", 30, "the App Center")
    time.sleep(8)


def search(vm, text: str) -> None:
    focus = atspi(vm, "focus", "Search applications", check=False)
    assert focus.returncode == 0, f"{focus.stdout}{focus.stderr}\n{dump(vm)[-2500:]}"
    time.sleep(1)
    vm.send_keys("ctrl-a")
    vm.type_text(text)
    time.sleep(3)


def test_catalogue_loads_and_search_finds_applications(vm, logdir, record_property):
    boot(vm, logdir, "appcenter")
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
    log_in_at_greeter(vm, logdir, "appcenter")
    wait_for(
        vm,
        f"runuser -u {USER} -- flatpak remotes --user --columns=name | grep -qx flathub",
        120,
        "the per-user Flathub remote",
    )
    start_app_center(vm)
    search(vm, "chrome")
    seconds = wait_text(vm, "Google Chrome", 900, "the catalogue")
    record_property("seconds_to_catalogue", round(seconds, 1))
    log(logdir, "appcenter", f"catalogue and search result after {seconds:.0f} s")
    shot(vm, logdir, "appcenter-search")


def test_verified_publisher_is_explained_not_called_safe(vm, logdir):
    search(vm, "firefox")
    press(vm, "Firefox*")
    wait_text(vm, "Verified publisher", 60, "Firefox's page")
    shown = dump(vm)
    log(logdir, "appcenter-firefox", shown)
    assert "does not mean" in shown and "safe" in shown, "verification needs its explanation"
    wait_text(vm, "Network and the internet", 120, "Firefox's permissions")
    shot(vm, logdir, "appcenter-firefox")
    vm.send_keys("esc")
    time.sleep(2)


def test_install_shows_progress_and_installs_for_the_user_only(vm, logdir, record_property):
    if "Back to the list" in dump(vm):
        press(vm, "Back to the list")
    search(vm, "chrome")
    press(vm, "Google Chrome")
    wait_text(vm, "Install Google Chrome", 30, "Chrome's page")
    log(logdir, "appcenter-chrome", dump(vm))
    press(vm, "Install Google Chrome")
    started = time.monotonic()
    seen = set()
    while CHROME not in user_apps(vm):
        assert time.monotonic() - started < INSTALL_TIMEOUT_S, "Chrome was not installed"
        for line in dump(vm).splitlines():
            if "status bar" in line and ("%" in line or "Installing" in line):
                seen.add(line.split("|", 1)[1].strip())
        time.sleep(3)
    seconds = time.monotonic() - started
    record_property("seconds_to_install_chrome", round(seconds, 1))
    log(logdir, "appcenter", f"installed in {seconds:.0f} s; progress shown: {sorted(seen)[:12]}")
    assert seen, "no progress was shown while installing"
    assert not vm.ssh("flatpak list --system --app --columns=application").stdout.strip()
    wait_text(vm, "Open Google Chrome", 30, "the Open button")
    press(vm, "Open Google Chrome")
    wait_for(vm, f"pgrep -u {USER} -f /app/extra/chrome", 120, "Chrome")
    time.sleep(5)
    vm.ssh(f"pkill -u {USER} -f /app/extra/chrome", check=False)
    shot(vm, logdir, "appcenter-installed")


def test_update_is_announced_not_applied_then_installed_on_request(vm, logdir):
    log_text = as_user(vm, f"flatpak remote-info --user --log flathub {CHROME}", False).stdout
    commits = [
        line.split()[-1] for line in log_text.splitlines() if line.strip().startswith("Commit:")
    ]
    log(logdir, "appcenter", f"Chrome commits on Flathub: {commits[:3]}")
    if len(commits) < 2:
        pytest.skip("Flathub offers only one Chrome commit; no older version to update from")
    latest, older = commits[0], commits[1]
    result = as_user(
        vm,
        f"flatpak update --user --noninteractive -y --commit={older} {CHROME} 2>&1",
        check=False,
        timeout=INSTALL_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stdout[-2000:]

    def installed_commit() -> str:
        return as_user(vm, f"flatpak info --user --show-commit {CHROME}").stdout.strip()

    assert installed_commit().startswith(older[:12])
    in_session(vm, "aegis-appcenter --check-updates", timeout=180)
    assert installed_commit().startswith(older[:12]), "the daily check applied an update"
    start_app_center(vm)
    press(vm, "Updates")
    wait_text(vm, "Google Chrome", 180, "the Updates tab")
    shot(vm, logdir, "appcenter-updates")
    press(vm, "Update all applications")
    started = time.monotonic()
    while not installed_commit().startswith(latest[:12]):
        assert time.monotonic() - started < INSTALL_TIMEOUT_S, "the update was not installed"
        time.sleep(5)
    log(logdir, "appcenter", f"updated to {latest[:12]} in {time.monotonic() - started:.0f} s")


def status_bar(vm) -> str:
    return "\n".join(line for line in dump(vm).splitlines() if "status bar" in line)


def open_page(vm, tab: str, name: str) -> None:
    """Back to the list (a page may still be open), choose TAB, open NAME's page."""
    if "Back to the list" in dump(vm):
        press(vm, "Back to the list")
    press(vm, tab)
    press(vm, name)


def test_remove_and_a_plain_error_without_flathub(vm, logdir):
    open_page(vm, "Installed", "Google Chrome")
    press(vm, "Remove Google Chrome")
    started = time.monotonic()
    while CHROME in user_apps(vm):
        assert time.monotonic() - started < 300, f"Chrome was not removed: {status_bar(vm)}"
        time.sleep(3)
    vm.ssh(
        "cp /etc/hosts /etc/hosts.aegis-test && printf '127.0.0.1 dl.flathub.org flathub.org\\n' "
        ">> /etc/hosts"
    )
    try:
        vm.send_keys("esc")
        press(vm, "Discover")
        search(vm, "chrome")
        press(vm, "Google Chrome")
        press(vm, "Install Google Chrome")
        wait_text(vm, "No internet connection", 180, "the error message")
        shot(vm, logdir, "appcenter-offline")
    finally:
        vm.ssh("mv /etc/hosts.aegis-test /etc/hosts")
    assert CHROME not in user_apps(vm)


def test_an_installed_application_survives_a_power_off(vm, logdir):
    if "Back to the list" in dump(vm):
        press(vm, "Back to the list")
    press(vm, "Discover")
    search(vm, "chrome")
    press(vm, "Google Chrome")
    press(vm, "Install Google Chrome")
    started = time.monotonic()
    while CHROME not in user_apps(vm):
        assert time.monotonic() - started < INSTALL_TIMEOUT_S, "Chrome was not installed"
        time.sleep(3)
    vm.ssh("sync")
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0
    boot(vm, logdir, "appcenter second boot")
    log_in_at_greeter(vm, logdir, "appcenter-second")
    start_app_center(vm)
    press(vm, "Installed")
    wait_text(vm, "Google Chrome", 60, "the Installed tab after the power-off")
    log(logdir, "appcenter", "after the power-off, Installed tab shows Google Chrome")
    assert (
        as_user(vm, "systemctl --user is-enabled aegis-appcenter-updates.timer").stdout.strip()
        == "enabled"
    )
    denials = vm.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    log(logdir, "appcenter-denials", denials or "none")
    assert not denials.strip(), denials[:3000]
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0

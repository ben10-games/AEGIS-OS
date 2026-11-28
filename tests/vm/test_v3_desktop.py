"""AEGIS OS v3 (M10): the hybrid AEGIS desktop on the persistent VDI, driven with the
keyboard and checked through KWin.

The exported VDI on VirtualBox-like hardware (QEMU, not VirtualBox), offline. The
account is created through the setup socket; the user logs in by typing the password
at the AEGIS login screen. Then: the top bar and the dock (geometry from KWin), the
widgets load without QML errors, Quick Settings actions change the real settings and
Meta+A opens the panel, the keyboard shortcuts start what they promise, windows snap and
maximise with Meta+arrows (geometry from KWin), the AEGIS typeface and window switcher
are in effect, and screenshots at three screen sizes in AEGIS Dark and AEGIS Light for
visual review (all in the uploaded logs, a few in the job log), and the screen reader (Orca)
starts with Meta+Alt+S.
"""

from __future__ import annotations

import base64
import json
import re
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

QUICK = "/usr/libexec/aegis/quick-settings"


@pytest.fixture(scope="module")
def vm(vdi, workdir, logdir, accel):  # noqa: F811
    with vdi_machine(vdi, workdir, logdir, accel, "v3-desktop", cpus=2) as machine:
        yield machine


def in_session(vm, command: str, check: bool = True, timeout: float = 60):
    """Run a command through the user's systemd manager, with the session environment."""
    return as_user(
        vm, f"systemd-run --user --wait --pipe --quiet {command}", check=check, timeout=timeout
    )


def kwin(vm, script: str, marker: str) -> list[list[str]]:
    """Run a KWin script; return the fields of each line it logged after MARKER."""
    encoded = base64.b64encode(script.encode()).decode()
    vm.ssh(f"echo {encoded} | base64 -d > /tmp/aegis-q.js && chmod 0644 /tmp/aegis-q.js")
    since = vm.ssh("date '+%Y-%m-%d %H:%M:%S'").stdout.strip()
    call = "busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting"
    as_user(vm, f"{call} unloadScript s aegisq", check=False)
    number = as_user(vm, f"{call} loadScript ss /tmp/aegis-q.js aegisq").stdout.split()[-1]
    as_user(
        vm, f"busctl --user call org.kde.KWin /Scripting/Script{number} org.kde.kwin.Script run"
    )
    for _ in range(10):
        time.sleep(1)
        out = as_user(vm, f'journalctl --user --since "{since}" -o cat', check=False).stdout
        rows = [
            line.split(marker + " ", 1)[1].split() for line in out.splitlines() if marker in line
        ]
        if rows:
            return rows
    raise AssertionError(f"KWin printed nothing for {marker}")


PANELS = """
const s = workspace.virtualScreenSize;
for (const w of workspace.windowList()) {
    if (w.dock) {
        const g = w.frameGeometry;
        console.info("AEGIS-PANEL " + s.width + " " + s.height + " " + Math.round(g.x) + " "
            + Math.round(g.y) + " " + Math.round(g.width) + " " + Math.round(g.height));
    }
}
"""

ACTIVE = """
const w = workspace.activeWindow;
const a = workspace.clientArea(KWin.MaximizeArea, w);
const g = w.frameGeometry;
console.info("AEGIS-ACTIVE " + w.resourceClass + " " + Math.round(g.x) + " " + Math.round(g.y)
    + " " + Math.round(g.width) + " " + Math.round(g.height) + " " + Math.round(a.x) + " "
    + Math.round(a.y) + " " + Math.round(a.width) + " " + Math.round(a.height));
"""


def panels(vm) -> list[tuple[int, ...]]:
    return [tuple(int(v) for v in row) for row in kwin(vm, PANELS, "AEGIS-PANEL")]


def active_window(vm) -> tuple[str, list[int]]:
    row = kwin(vm, ACTIVE, "AEGIS-ACTIVE")[-1]
    return row[0], [int(v) for v in row[1:]]


def changed_bytes(a: bytes, b: bytes) -> int:
    return sum(1 for x, y in zip(a, b, strict=False) if x != y)


def test_login_screen_is_the_aegis_theme(vm, logdir):
    boot(vm, logdir, "desktop")
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
    wait_for(vm, "pgrep -f sddm-greeter", 180, "the login screen")
    greeter = vm.ssh("pgrep -af sddm-greeter").stdout
    log(logdir, "desktop", f"greeter: {greeter.strip()}")
    assert "themes/aegis" in greeter, greeter
    log_in_at_greeter(vm, logdir, "desktop")  # types the password: the field has the focus
    time.sleep(20)


def test_top_bar_and_dock(vm, logdir):
    found = panels(vm)
    log(logdir, "desktop", f"panels (screen w h, x y w h): {found}")
    assert len(found) == 2, found
    top = min(found, key=lambda p: p[3])
    dock = max(found, key=lambda p: p[3])
    sw, sh = top[0], top[1]
    assert top[3] == 0 and top[2] == 0 and top[4] == sw, f"top bar {top}"
    assert top[5] <= 48, f"top bar too tall: {top}"
    assert abs((dock[2] + dock[4] / 2) - sw / 2) <= 4, f"dock not centred: {dock}"
    assert sh - 40 <= dock[3] + dock[5] <= sh, f"dock not at the bottom: {dock}"
    applets = vm.ssh(f"cat /var/home/{USER}/.config/plasma-org.kde.plasma.desktop-appletsrc").stdout
    for plugin in (
        "org.aegisos.activewindow",
        "org.kde.milou",
        "org.aegisos.quicksettings",
        "org.kde.plasma.systemtray",
        "org.kde.plasma.digitalclock",
        "org.kde.plasma.kickoff",
        "org.aegisos.security",
    ):
        assert f"plugin={plugin}" in applets, plugin
    errors = vm.ssh(
        'journalctl -b -o cat --no-pager | grep -iE "org/aegisos|org.aegisos" '
        '| grep -iE "error|unavailable|is not a type|cannot assign" || true'
    ).stdout
    log(logdir, "desktop-qml-errors", errors or "none")
    assert not errors.strip(), errors[:3000]
    shot(vm, logdir, "desktop-1920-dark")


def test_quick_settings_actions_change_real_settings(vm, logdir):
    status = in_session(vm, f"{QUICK} status").stdout
    log(logdir, "desktop", f"quick settings status:\n{status}")
    assert "scheme=" in status and "glass=" in status
    in_session(vm, f"{QUICK} scheme light")
    assert "scheme=AEGISLight" in in_session(vm, f"{QUICK} status").stdout
    in_session(vm, f"{QUICK} nightlight on")
    assert "nightlight=on" in in_session(vm, f"{QUICK} status").stdout
    in_session(vm, f"{QUICK} nightlight off")
    in_session(vm, f"{QUICK} scheme dark")
    assert "scheme=AEGISDark" in in_session(vm, f"{QUICK} status").stdout


def test_meta_a_opens_quick_settings(vm, logdir):
    time.sleep(3)
    before = shot(vm, logdir, "before-quick").read_bytes()
    vm.send_keys("meta_l-a")
    time.sleep(3)
    opened = shot(vm, logdir, "quick-settings").read_bytes()
    vm.send_keys("esc")
    time.sleep(2)
    changed = changed_bytes(before, opened)
    log(logdir, "desktop", f"Meta+A: {changed} bytes of the screen changed")
    assert changed > 50000, "Quick Settings did not open"


@pytest.mark.parametrize(
    ("keys", "process"),
    [
        ("meta_l-e", "dolphin"),
        ("ctrl-alt-t", "konsole"),
        ("meta_l-i", "systemsettings"),
        ("meta_l-shift-s", "spectacle"),
    ],
)
def test_shortcut_starts_its_application(vm, logdir, keys, process):
    vm.send_keys(keys)
    seconds = wait_for(vm, f"pgrep -u {USER} -x {process}", 30, f"{process} after {keys}")
    log(logdir, "desktop", f"{keys}: {process} started after {seconds:.1f} s")
    time.sleep(3)
    if process == "spectacle":
        # Close the area selection as a person would: killing Spectacle while its
        # full-screen overlay was up once ended the session (run 46058727757).
        vm.send_keys("esc")
        time.sleep(2)
    vm.ssh(f"pkill -u {USER} -x {process}", check=False)
    time.sleep(2)


def test_windows_snap_and_maximise_with_meta_arrows(vm, logdir):
    vm.send_keys("ctrl-alt-t")
    wait_for(vm, f"pgrep -u {USER} -x konsole", 30, "Konsole")
    time.sleep(4)
    results = {}
    # Meta+Up on a half tile makes a quarter tile (KWin, like Windows' quarter snapping);
    # Meta+PgUp maximises (run 46021359536).
    for keys, label in (("meta_l-left", "left"), ("meta_l-right", "right"), ("meta_l-pgup", "max")):
        vm.send_keys(keys)
        time.sleep(2)
        name, (x, y, w, h, ax, ay, aw, ah) = active_window(vm)
        results[label] = (name, x, y, w, h, ax, ay, aw, ah)
        log(logdir, "desktop", f"{keys}: {name} at {x},{y} {w}x{h} in area {ax},{ay} {aw}x{ah}")
        assert "konsole" in name.lower(), name
        assert ay >= 20, "the maximise area must leave the top bar visible"
        if label == "left":
            assert x == ax and abs(w - aw / 2) <= 2 and abs(h - ah) <= 2, results[label]
        elif label == "right":
            assert x + w == ax + aw and abs(w - aw / 2) <= 2, results[label]
        else:
            assert (x, y, w, h) == (ax, ay, aw, ah), results[label]
    shot(vm, logdir, "snapped")
    vm.ssh(f"pkill -u {USER} -x konsole", check=False)


def test_typeface_and_window_switcher(vm, logdir):
    # Read inside the session: the AEGIS look-and-feel defaults live in ~/.config/kdedefaults,
    # which Plasma adds to the session's XDG_CONFIG_DIRS (run 46021359536 read them outside).
    font = in_session(vm, "kreadconfig6 --file kdeglobals --group General --key font").stdout
    switcher = in_session(vm, "kreadconfig6 --file kwinrc --group TabBox --key LayoutName").stdout
    matched = vm.ssh("fc-match Inter").stdout
    log(logdir, "desktop", f"font: {font.strip()}; Alt+Tab: {switcher.strip()}; {matched}")
    assert font.startswith("Inter,"), font
    assert switcher.strip() == "thumbnail_grid", switcher
    assert "Inter" in matched


@pytest.mark.parametrize("size", ["1366x768", "1920x1080", "largest"])
def test_screenshots_at_three_sizes_dark_and_light(vm, logdir, size):
    outputs = re.sub(r"\x1b\[[0-9;]*m", "", in_session(vm, "kscreen-doctor --outputs").stdout)
    output = re.search(r"^Output:\s+\d+\s+(\S+)", outputs, re.M).group(1)
    modes = [(m[0], int(m[1]), int(m[2])) for m in re.findall(r"(\d+):(\d+)x(\d+)@", outputs)]
    if size == "largest":
        mode = max(modes, key=lambda m: m[1] * m[2])
    else:
        w, h = (int(v) for v in size.split("x"))
        mode = next(m for m in modes if (m[1], m[2]) == (w, h))
    in_session(vm, f"kscreen-doctor output.{output}.mode.{mode[0]}")
    time.sleep(6)
    found = panels(vm)
    log(logdir, "desktop", f"{size} ({mode[1]}x{mode[2]}): panels {found}")
    top = min(found, key=lambda p: p[3])
    assert top[4] == top[0], "the top bar does not span the screen"
    label = size.split("x")[0] if size != "largest" else "largest"
    for scheme in ("dark", "light"):
        in_session(vm, f"{QUICK} scheme {scheme}")
        time.sleep(4)
        shot(vm, logdir, f"desktop-{label}-{scheme}")
    in_session(vm, f"{QUICK} scheme dark")


# The accessibility bus status and the applications on it. Sent
# base64-encoded: as_user wraps commands in single quotes, which broke an inline script
# (run 46085976334) and the quoting gdbus needs (run 46089483800).
A11Y = """
from gi.repository import Gio
import pyatspi
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
status = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.NONE, None, "org.a11y.Bus",
                                "/org/a11y/bus", "org.a11y.Status", None)
print("status", {name: status.get_cached_property(name).unpack()
                 for name in status.get_cached_property_names() or []})
print("applications", " ".join(str(a.name) for a in pyatspi.Registry.getDesktop(0)))
"""
KACCESS = "kreadconfig6 --file kaccessrc --group ScreenReader --key Enabled"


def a11y_state(vm) -> dict[str, str]:
    script = base64.b64encode(A11Y.encode()).decode()
    vm.ssh(f"echo {script} | base64 -d > /tmp/aegis-a11y.py && chmod 0644 /tmp/aegis-a11y.py")
    result = in_session(vm, "python3 /tmp/aegis-a11y.py", check=False)
    state = dict(line.split(" ", 1) for line in result.stdout.splitlines() if " " in line)
    state["errors"] = result.stderr.strip()[-1500:]
    return state


def test_screen_reader_starts_with_its_shortcut(vm, logdir, record_property):
    """M13 accessibility: Meta+Alt+S (KDE's screen-reader shortcut) starts Orca, which
    keeps running and joins the accessibility bus (speech through speech-dispatcher)."""
    vm.send_keys("meta_l-alt-s")
    seconds = wait_for(vm, f"pgrep -u {USER} -f /usr/bin/orca", 30, "Orca after Meta+Alt+S")
    record_property("seconds_to_screen_reader", round(seconds, 1))
    time.sleep(8)
    assert vm.ssh(f"pgrep -u {USER} -f /usr/bin/orca", check=False).returncode == 0, (
        "Orca exited after starting:\n"
        + as_user(vm, "journalctl --user -b -o cat | grep -i orca | tail -40", False).stdout
    )
    on = a11y_state(vm)
    setting = as_user(vm, KACCESS, check=False).stdout.strip()
    speech = vm.ssh(f"pgrep -u {USER} -a speech-dispatch", check=False).stdout.strip()
    log(
        logdir,
        "desktop",
        f"Meta+Alt+S: Orca after {seconds:.1f} s; accessibility bus: {on}; "
        f"kaccessrc Enabled={setting or '(not set)'}; speech: {speech or 'not running'}",
    )
    assert "orca" in on.get("applications", "").split(), on
    # Turning it off again is recorded, not yet asserted: run 46092984886 showed that this
    # at-spi2-core has no ScreenReaderEnabled property, so what "off" looks like here is
    # taken from a run before it is required.
    vm.send_keys("meta_l-alt-s")
    time.sleep(5)
    off = a11y_state(vm)
    still = vm.ssh(f"pgrep -u {USER} -f /usr/bin/orca", check=False).returncode == 0
    log(logdir, "desktop", f"Meta+Alt+S again: {off}; Orca still running: {still}")
    vm.ssh(f"pkill -u {USER} -f /usr/bin/orca", check=False)
    time.sleep(2)


def test_no_failed_units_or_denials(vm, logdir):
    failed = vm.ssh("systemctl --failed --no-legend --plain").stdout.strip()
    denials = vm.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    log(logdir, "desktop-denials", denials or "none")
    assert not failed, failed
    assert not denials.strip(), denials[:3000]
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0

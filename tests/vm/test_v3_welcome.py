"""AEGIS OS v3 (M11): "Welcome to AEGIS", the interactive tour, driven by real input.

The exported VDI on VirtualBox-like hardware (QEMU, not VirtualBox), offline. After the
first login the tour starts by itself. The test then works through all seven scenes the
way a person would:

- keyboard through QEMU's virtual keyboard: Alt+Right/Left between scenes, the Meta key
  for the launcher, Meta+E for Files, Alt+F7/Alt+F8 and arrows to move and resize a real
  window, Meta+Left / Meta+PgUp / Meta+PgDown to snap, maximise and minimise it;
- the mouse through QEMU's tablet: a real drag and drop onto the practice dock;
- the accessibility interface (AT-SPI, as a screen reader would): the other controls
  are found by their accessible names and activated, which also shows that every control
  of the tour can be used without a mouse.

Each exercise must be reported done by the tour itself (its D-Bus object, read-only),
which completes them only from the real events KWin reports. Then: progress survives a
restart, a finished tour does not start again after a power-off, replay and skip work,
reduced motion is honoured, no QML errors, no SELinux denials. CPU use during the opening
animation is measured and recorded.
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

BUS = "busctl --user {} org.aegisos.Welcome /Welcome org.aegisos.Welcome"
STATE = f"/var/home/{USER}/.local/state/aegis/welcome.json"

ATSPI = r"""
import sys
import pyatspi

def walk(node):
    yield node
    for i in range(node.childCount):
        child = node.getChildAtIndex(i)
        if child is not None:
            yield from walk(child)

APPS = ("aegis-welcome", "Welcome to AEGIS")

def apps():
    desktop = pyatspi.Registry.getDesktop(0)
    every = [app for app in desktop if app is not None]
    named = [app for app in every if app.name in APPS]
    return named or every  # names differ between toolkits: then look everywhere

def nodes():
    for app in apps():
        yield from walk(app)

def find(name):
    prefix = name.endswith("*")
    name = name.rstrip("*")
    for node in nodes():
        try:
            label = node.name or ""
            showing = node.getState().contains(pyatspi.STATE_SHOWING)
        except Exception:
            continue
        if showing and (label == name or (prefix and label.startswith(name))):
            return node
    return None

command, name = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""
if command == "dump":
    try:
        print("applications:", [app.name for app in pyatspi.Registry.getDesktop(0) if app])
    except Exception as error:
        print("no accessibility bus:", repr(error))
    for node in nodes():
        try:
            if node.getState().contains(pyatspi.STATE_SHOWING) and node.name:
                print(node.getRoleName(), "|", node.name)
        except Exception:
            pass
    sys.exit(0)
node = find(name)
if node is None:
    print("not found:", name)
    sys.exit(3)
if command == "press":
    node.queryAction().doAction(0)
elif command == "focus":
    node.queryComponent().grabFocus()
elif command == "extents":
    e = node.queryComponent().getExtents(pyatspi.WINDOW_COORDS)
    print(e.x, e.y, e.width, e.height)
"""

WINDOW = """
const s = workspace.virtualScreenSize;
for (const w of workspace.windowList()) {
    if (String(w.resourceClass) === "org.aegisos.welcome") {
        const g = w.clientGeometry;
        console.info("AEGIS-WELCOME " + s.width + " " + s.height + " " + Math.round(g.x) + " "
            + Math.round(g.y) + " " + Math.round(g.width) + " " + Math.round(g.height));
    }
}
"""


@pytest.fixture(scope="module")
def vm(vdi, workdir, logdir, accel):  # noqa: F811
    with vdi_machine(vdi, workdir, logdir, accel, "v3-welcome", cpus=2) as machine:
        yield machine


def in_session(vm, command: str, check: bool = True, timeout: float = 60):
    return as_user(
        vm, f"systemd-run --user --wait --pipe --quiet {command}", check=check, timeout=timeout
    )


def atspi(vm, *arguments: str, check: bool = True):
    script = base64.b64encode(ATSPI.encode()).decode()
    quoted = " ".join(json.dumps(a) for a in arguments)
    vm.ssh(f"echo {script} | base64 -d > /tmp/aegis-atspi.py && chmod 0644 /tmp/aegis-atspi.py")
    return in_session(vm, f"python3 /tmp/aegis-atspi.py {quoted}", check=check)


def press(vm, name: str) -> None:
    for _ in range(10):
        if atspi(vm, "press", name, check=False).returncode == 0:
            time.sleep(1.5)
            return
        time.sleep(1)
    dump = atspi(vm, "dump", check=False).stdout
    raise AssertionError(f"no control named {name!r}; showing:\n{dump[-3000:]}")


def prop(vm, name: str) -> str:
    return as_user(vm, BUS.format("get-property") + f" {name}", check=False).stdout.strip()


def completed(vm) -> list[str]:
    reply = prop(vm, "completed")
    return [item.strip('"') for item in reply.split()[2:]] if reply.startswith("as") else []


def scene(vm) -> int:
    reply = prop(vm, "scene").split()
    return int(reply[1]) if len(reply) == 2 else -1


def wait_done(vm, step: str, deadline_s: float = 20) -> None:
    started = time.monotonic()
    while time.monotonic() - started < deadline_s:
        if step in completed(vm):
            return
        time.sleep(1)
    raise AssertionError(
        f"{step} was not completed; completed: {completed(vm)}; "
        f"last window event: {prop(vm, 'lastEvent')}"
    )


def kwin_lines(vm, script: str, marker: str) -> list[list[str]]:
    encoded = base64.b64encode(script.encode()).decode()
    vm.ssh(f"echo {encoded} | base64 -d > /tmp/aegis-w.js && chmod 0644 /tmp/aegis-w.js")
    since = vm.ssh("date '+%Y-%m-%d %H:%M:%S'").stdout.strip()
    call = "busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting"
    as_user(vm, f"{call} unloadScript s aegisw", check=False)
    number = as_user(vm, f"{call} loadScript ss /tmp/aegis-w.js aegisw").stdout.split()[-1]
    as_user(
        vm, f"busctl --user call org.kde.KWin /Scripting/Script{number} org.kde.kwin.Script run"
    )
    for _ in range(10):
        time.sleep(1)
        out = as_user(vm, f'journalctl --user --since "{since}" -o cat', check=False).stdout
        rows = [x.split(marker + " ", 1)[1].split() for x in out.splitlines() if marker in x]
        if rows:
            return rows
    raise AssertionError(f"KWin printed nothing for {marker}")


def start_tour(vm, *arguments: str) -> None:
    """Start the tour in the session, with the accessibility bridge on."""
    # Without --wait (run 46023524801: in_session's --wait cannot be combined with
    # --no-block, so the tour never started).
    as_user(
        vm,
        "systemd-run --user --collect --quiet "
        "--setenv=QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 aegis-welcome " + " ".join(arguments),
        check=False,
    )
    wait_for(vm, f"pgrep -u {USER} -x aegis-welcome", 30, "the tour")
    time.sleep(6)


def cpu_ticks(vm, name: str) -> int:
    out = vm.ssh(
        f"for p in $(pgrep -u {USER} -x {name}); do awk '{{print $14+$15}}' /proc/$p/stat; done",
        check=False,
    ).stdout
    return sum(int(v) for v in out.split())


def test_tour_starts_by_itself_after_the_first_login(vm, logdir, record_property):
    boot(vm, logdir, "welcome")
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
    log_in_at_greeter(vm, logdir, "welcome", keep_tour=True)
    seconds = wait_for(vm, f"pgrep -u {USER} -x aegis-welcome", 60, "the tour to start by itself")
    log(logdir, "welcome", f"tour started {seconds:.1f} s after the desktop processes")
    # The opening animation: CPU use of the tour and of KWin while it plays.
    hz = int(vm.ssh("getconf CLK_TCK").stdout.strip() or 100)
    before = {n: cpu_ticks(vm, n) for n in ("aegis-welcome", "kwin_wayland")}
    time.sleep(4)
    after = {n: cpu_ticks(vm, n) for n in ("aegis-welcome", "kwin_wayland")}
    shares = {n: round(100 * (after[n] - before[n]) / hz / 4) for n in before}
    log(logdir, "welcome", f"opening animation, CPU (100% = one CPU): {shares}")
    record_property("cpu_opening_animation", json.dumps(shares))
    shot(vm, logdir, "welcome-1")
    assert scene(vm) == 0
    assert "true" in prop(vm, "watching"), "KWin did not load the window watcher"


def test_progress_survives_a_restart_of_the_tour(vm):
    vm.send_keys("alt-right")
    time.sleep(2)
    assert scene(vm) == 1
    vm.ssh(f"pkill -u {USER} -x aegis-welcome")
    time.sleep(2)
    start_tour(vm)
    assert scene(vm) == 1, "the tour did not resume at the scene it was on"


def test_scene_2_launcher_files_and_drag_and_drop(vm, logdir):
    shot(vm, logdir, "welcome-2")
    vm.send_keys("meta_l")
    wait_done(vm, "desktop.launcher")
    vm.send_keys("esc")
    time.sleep(2)
    vm.send_keys("meta_l-e")
    wait_done(vm, "desktop.files")
    time.sleep(3)
    # The tour stays above other windows (watch.js); drag "Files" onto the practice dock.
    sw, sh, wx, wy, _, _ = (int(v) for v in kwin_lines(vm, WINDOW, "AEGIS-WELCOME")[-1])
    icon = [int(v) for v in atspi(vm, "extents", "Place Files on the practice dock").stdout.split()]
    dock = [int(v) for v in atspi(vm, "extents", "Practice dock").stdout.split()]
    x1, y1 = wx + icon[0] + icon[2] / 2, wy + icon[1] + icon[3] / 2
    x2, y2 = wx + dock[0] + dock[2] / 2, wy + dock[1] + dock[3] / 2
    log(logdir, "welcome", f"drag from {x1:.0f},{y1:.0f} to {x2:.0f},{y2:.0f} on {sw}x{sh}")
    vm.drag(x1 / sw, y1 / sh, x2 / sw, y2 / sh)
    wait_done(vm, "desktop.drag")


def test_scene_3_moves_resizes_snaps_maximises_and_minimises_a_real_window(vm, logdir):
    press(vm, "Next")
    assert scene(vm) == 2
    press(vm, "Open a Files window to practise with")
    time.sleep(5)  # the new window is in front
    vm.send_keys("alt-f7", *["right"] * 12, "ret")
    wait_done(vm, "workspace.move")
    vm.send_keys("alt-f8", *["right"] * 12, "ret")
    wait_done(vm, "workspace.resize")
    vm.send_keys("meta_l-left")
    wait_done(vm, "workspace.snap")
    vm.send_keys("meta_l-pgup")
    wait_done(vm, "workspace.maximise")
    shot(vm, logdir, "welcome-3")
    vm.send_keys("meta_l-pgdn")
    wait_done(vm, "workspace.minimise")


def test_scene_4_changes_the_real_desktop_and_undoes(vm, logdir):
    press(vm, "Next")
    assert scene(vm) == 3
    press(vm, "AEGIS Light")
    light = as_user(vm, "kreadconfig6 --file kdeglobals --group General --key ColorScheme").stdout
    assert light.strip() == "AEGISLight", light
    press(vm, "Liquid Glass Performance")
    press(vm, "Wallpaper *")  # the first wallpaper offered
    shot(vm, logdir, "welcome-4")
    for step in ("yours.scheme", "yours.glass", "yours.wallpaper"):
        wait_done(vm, step)
    press(vm, "Undo the changes made in this step")
    dark = as_user(vm, "kreadconfig6 --file kdeglobals --group General --key ColorScheme").stdout
    assert dark.strip() == "AEGISDark", "Undo did not restore AEGIS Dark"


def test_scene_5_finds_an_application_and_its_permissions(vm, logdir):
    press(vm, "Next")
    assert scene(vm) == 4
    assert atspi(vm, "focus", "Search applications", check=False).returncode == 0
    time.sleep(1)
    vm.type_text("browser")
    wait_done(vm, "apps.search")
    press(vm, "Google Chrome")
    wait_done(vm, "apps.details")
    dump = atspi(vm, "dump").stdout
    log(logdir, "welcome-apps", dump)
    assert "Verified publisher" in dump, dump[-2000:]
    assert "does not" in dump and "safe" in dump, "verification must not read as a safety claim"
    shot(vm, logdir, "welcome-5")


def test_scene_6_security_cards_show_the_real_state(vm, logdir):
    press(vm, "Next")
    assert scene(vm) == 5
    for card in ("Sealed system: *", "SELinux: *", "Secure Boot: *"):
        press(vm, card)
    wait_done(vm, "security.explore")
    dump = atspi(vm, "dump").stdout
    log(logdir, "welcome-security", dump)
    assert "SELinux: Enforcing" in dump, dump[-2000:]
    shot(vm, logdir, "welcome-6")


def test_scene_7_finishes_the_tour(vm, logdir):
    press(vm, "Next")
    assert scene(vm) == 6
    time.sleep(2)
    shot(vm, logdir, "welcome-7")
    done = completed(vm)
    log(logdir, "welcome", f"completed {len(done)}: {done}")
    assert len(done) == 14, done
    press(vm, "Start using AEGIS")
    wait_for(vm, f"! pgrep -u {USER} -x aegis-welcome", 20, "the tour to close")
    state = json.loads(vm.ssh(f"cat {STATE}").stdout)
    log(logdir, "welcome", f"saved state: {state}")
    assert state["done"] is True and state["skipped"] is False


def test_replay_skip_and_reduced_motion(vm, logdir):
    start_tour(vm, "--replay")
    assert scene(vm) == 0 and completed(vm) == []
    press(vm, "Skip the tour")
    press(vm, "Leave the tour")
    wait_for(vm, f"! pgrep -u {USER} -x aegis-welcome", 20, "the tour to close after Skip")
    assert json.loads(vm.ssh(f"cat {STATE}").stdout)["skipped"] is True
    as_user(vm, "kwriteconfig6 --file kdeglobals --group KDE --key AnimationDurationFactor 0")
    start_tour(vm, "--replay")
    assert "true" in prop(vm, "reducedMotion"), "KDE's reduced motion was not honoured"
    shot(vm, logdir, "welcome-reduced-motion")
    as_user(vm, "kwriteconfig6 --file kdeglobals --group KDE --key AnimationDurationFactor 1")
    press(vm, "Skip the tour")
    press(vm, "Leave the tour")
    wait_for(vm, f"! pgrep -u {USER} -x aegis-welcome", 20, "the tour to close")


def test_a_finished_tour_does_not_start_again_after_a_power_off(vm, logdir):
    errors = vm.ssh(
        "journalctl -b -o cat --no-pager | grep -iE 'aegis-welcome|AegisWelcome' "
        "| grep -iE 'error|is not a type|cannot assign|unavailable|ReferenceError|TypeError' "
        "|| true"
    ).stdout
    log(logdir, "welcome-qml-errors", errors or "none")
    assert not errors.strip(), errors[:3000]
    vm.ssh("sync")
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0
    boot(vm, logdir, "welcome second boot")
    log_in_at_greeter(vm, logdir, "welcome-second", keep_tour=True)
    time.sleep(30)
    assert vm.ssh(f"pgrep -u {USER} -x aegis-welcome", check=False).returncode != 0
    denials = vm.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    log(logdir, "welcome-denials", denials or "none")
    assert not denials.strip(), denials[:3000]
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0

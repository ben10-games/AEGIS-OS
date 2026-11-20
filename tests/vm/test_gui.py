"""M4-GUI and GUI v1: the graphical development image (aegis-gui) under Secure Boot.

The image ships no user. For this test the harness creates one at boot and asks SDDM
to log it in automatically, through systemd credentials in the firmware tables, the
same channel as the developer SSH key; nothing of it is in the image:

- sysusers.extra: the user 'aegisuser' (uid 1000, no password),
- tmpfiles.extra: its home directory and an SDDM autologin drop-in.

Tests run in order against one virtual machine with a virtio GPU, USB keyboard and
tablet, and an HDA sound card. Screenshots go to the log directory.
"""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path

import pytest
from conftest import machine

USER = "aegisuser"
UID = 1000
RUNTIME = f"/run/user/{UID}"
EFI_GLOBAL = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
SESSION_DEADLINE_S = 240
POWER_DOWN = re.compile(r"reboot: Power down")
FAILED_UNIT = re.compile(r"\[FAILED\][^\n]*")

TEST_USER_CREDENTIALS = (
    "io.systemd.credential.binary:sysusers.extra="
    + base64.b64encode(
        f'u {USER} {UID} "AEGIS test user" /var/home/{USER} /bin/bash\n'.encode()
    ).decode(),
    "io.systemd.credential.binary:tmpfiles.extra="
    + base64.b64encode(
        (
            f"d /var/home/{USER} 0700 {USER} {USER} -\n"
            "f+ /etc/sddm.conf.d/50-aegis-test-autologin.conf 0644 root root - "
            f"[Autologin]\\nUser={USER}\\nSession=plasma.desktop\\nRelogin=false\\n\n"
        ).encode()
    ).decode(),
)


@pytest.fixture(scope="module")
def gui(request, workdir, logdir, accel, secure_boot_firmware):
    disk = Path(request.config.getoption("--gui-disk")).resolve()
    with machine(disk, "test_gui", workdir, logdir, accel, secure_boot_firmware,
                 smbios_strings=TEST_USER_CREDENTIALS, graphics=True) as vm:  # fmt: skip
        vm.start()
        vm.wait_for_ssh(180)
        yield vm


def as_user(vm, command: str, check: bool = True, timeout: float = 60):
    """Run a command as the logged-in user, inside the user's session environment."""
    environment = (
        f"XDG_RUNTIME_DIR={RUNTIME} DBUS_SESSION_BUS_ADDRESS=unix:path={RUNTIME}/bus "
        "WAYLAND_DISPLAY=wayland-0 QT_QPA_PLATFORM=wayland"
    )
    return vm.ssh(
        f"runuser -u {USER} -- env {environment} sh -c '{command}'", check=check, timeout=timeout
    )


def wait_for(vm, command: str, deadline_s: float, what: str) -> float:
    started = time.monotonic()
    while time.monotonic() - started < deadline_s * vm.timeout_scale:
        if vm.ssh(command, check=False, timeout=30).returncode == 0:
            return time.monotonic() - started
        time.sleep(3)
    raise AssertionError(f"{what} did not happen within {deadline_s} s")


def shot(vm, logdir: Path, name: str) -> Path:
    return vm.screenshot(logdir / f"gui-{name}.ppm", fmt="ppm")


def launch(vm, application: str) -> None:
    """Start an application as the user, as a transient unit of the user's manager."""
    as_user(vm, f"systemd-run --user --collect --unit=aegis-test-{application} {application}")


def wait_for_session(vm) -> float:
    return wait_for(
        vm,
        f"pgrep -u {USER} -x plasmashell && pgrep -u {USER} -x kwin_wayland",
        SESSION_DEADLINE_S,
        "a Plasma Wayland session",
    )


def test_gui_session_starts_on_wayland(gui, logdir, record_property):
    """Boot to a graphical session: SDDM logs the user in; KWin and Plasma run on Wayland."""
    seconds = wait_for_session(gui)
    record_property("seconds_from_ssh_to_session", round(seconds, 1))
    sessions = gui.ssh(f"loginctl list-sessions --no-legend | awk '$3 == \"{USER}\" {{print $1}}'")
    session = sessions.stdout.split()[0]
    kind = gui.ssh(f"loginctl show-session {session} -p Type --value").stdout.strip()
    (logdir / "gui-session.txt").write_text(
        gui.ssh(f"loginctl show-session {session}").stdout
        + gui.ssh(f"ps -o pid,etimes,rss,args -u {USER} --sort=-rss | head -n 25").stdout
    )
    assert kind == "wayland"
    time.sleep(15)  # let the desktop finish drawing
    shot(gui, logdir, "desktop")


def test_gui_idle_measurements(gui, logdir, record_property):
    """Performance baseline right after login, before any application is opened:
    memory in use, KWin and plasmashell memory, idle CPU over 20 s, startup time."""
    time.sleep(20)  # let the session settle

    def meminfo():
        fields = dict(
            line.split(":", 1) for line in gui.ssh("cat /proc/meminfo").stdout.splitlines()
        )
        return int(fields["MemTotal"].split()[0]), int(fields["MemAvailable"].split()[0])

    def cpu_ticks():
        values = [int(v) for v in gui.ssh("head -n 1 /proc/stat").stdout.split()[1:]]
        return sum(values), values[3] + values[4]  # total, idle + iowait

    total_a, idle_a = cpu_ticks()
    time.sleep(20)
    total_b, idle_b = cpu_ticks()
    busy = 100.0 * (1 - (idle_b - idle_a) / max(1, total_b - total_a))
    total, available = meminfo()

    def rss(name):
        out = gui.ssh(f"ps -C {name} -o rss= | awk '{{s+=$1}} END {{print s+0}}'").stdout
        return int(out.strip() or 0) // 1024

    renderer = as_user(
        gui,
        'journalctl --user -b -o cat | grep -m1 -iE "OpenGL renderer|llvmpipe|virgl"',
        check=False,
    ).stdout.strip()
    report = (
        f"idle memory in use (MiB): {(total - available) // 1024}\n"
        f"kwin_wayland RSS (MiB): {rss('kwin_wayland')}\n"
        f"plasmashell RSS (MiB): {rss('plasmashell')}\n"
        f"plasma-keyboard RSS (MiB): {rss('plasma-keyboard')}\n"
        f"idle CPU busy over 20 s (%, all CPUs): {busy:.1f}\n"
        f"startup: {gui.ssh('systemd-analyze').stdout.splitlines()[0]}\n"
        f"renderer: {renderer or 'not reported'}\n"
    )
    (logdir / "gui-idle.txt").write_text(report)
    record_property("idle_memory_mib", (total - available) // 1024)
    record_property("idle_cpu_percent", round(busy, 1))


def test_gui_glass_effects_and_no_onscreen_keyboard(gui, logdir):
    """KWin really runs the blur and contrast effects behind the translucent dock, and the
    on-screen keyboard is not started (it remains available in System Settings)."""
    loaded = {}
    for effect in ("blur", "contrast", "slidingpopups"):
        reply = as_user(
            gui,
            "busctl --user call org.kde.KWin /Effects org.kde.kwin.Effects "
            f"isEffectLoaded s {effect}",
            check=False,
        ).stdout.strip()
        loaded[effect] = reply
    (logdir / "gui-effects.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in loaded.items())
        + "\n\nsupported:\n"
        + as_user(
            gui,
            "busctl --user get-property org.kde.KWin /Effects org.kde.kwin.Effects loadedEffects",
            check=False,
        ).stdout
    )
    assert loaded["blur"] == "b true", loaded
    assert loaded["contrast"] == "b true", loaded
    assert gui.ssh("pgrep -x plasma-keyboard", check=False).returncode != 0, (
        "the on-screen keyboard is running"
    )


def test_gui_dock_layout(gui, logdir):
    """The AEGIS dock: floating panel with the AEGIS launcher mark, pinned applications
    and the AEGIS Security widget, as written by the look-and-feel layout script."""
    applets = gui.ssh(
        f"cat /var/home/{USER}/.config/plasma-org.kde.plasma.desktop-appletsrc"
    ).stdout
    (logdir / "gui-applets.txt").write_text(applets)
    for plugin in (
        "org.kde.plasma.kickoff",
        "org.kde.plasma.icontasks",
        "org.aegisos.security",
        "org.kde.plasma.systemtray",
    ):
        assert f"plugin={plugin}" in applets, plugin
    assert "icon=aegis-os" in applets
    assert "org.kde.dolphin.desktop" in applets


def test_gui_security_dashboard(gui, logdir):
    """AEGIS Security Dashboard v0: its read-only helper reports the true state when run
    as the desktop user, and the widget (rendered by plasmawindowed) loads without QML
    errors. Screenshot inspected for the report."""
    facts = dict(
        line.split("=", 1)
        for line in as_user(gui, "/usr/libexec/aegis/security-status").stdout.splitlines()
        if "=" in line
    )
    (logdir / "gui-security-status.txt").write_text("\n".join(f"{k}={v}" for k, v in facts.items()))
    assert facts["selinux"] == "Enforcing"
    assert facts["secureboot"] == "enabled"
    assert facts["root"] == "sealed-composefs"
    assert facts["cmdline_check"] == "active"
    assert facts["firewall"] == "active"
    assert facts["lockdown"] == "integrity"
    assert facts["root_digest"] in gui.ssh("cat /proc/cmdline").stdout
    assert facts["updates"].startswith("unavailable"), "the helper must not have root"
    as_user(
        gui,
        "systemd-run --user --collect --unit=aegis-test-dashboard "
        "plasmawindowed org.aegisos.security",
    )
    wait_for(gui, f"pgrep -u {USER} -x plasmawindowed", 60, "the security widget window")
    time.sleep(10)
    shot(gui, logdir, "security-dashboard")
    errors = as_user(
        gui,
        'journalctl --user -b -o cat | grep -iE "aegisos|org/aegisos" '
        '| grep -iE "error|cannot|not installed|failed" || true',
    ).stdout
    (logdir / "gui-qml-errors.txt").write_text(errors)
    assert not errors.strip(), errors[:3000]
    gui.ssh(f"pkill -u {USER} -x plasmawindowed", check=False)


def test_gui_security_properties_are_kept(gui, logdir):
    """Secure Boot, SELinux enforcing, the sealed command line check; no denials."""
    secure_boot = gui.ssh(
        f"od -An -tu1 -j4 -N1 /sys/firmware/efi/efivars/SecureBoot-{EFI_GLOBAL}"
    ).stdout.split()
    assert secure_boot == ["1"]
    assert gui.ssh("getenforce").stdout.strip() == "Enforcing"
    assert gui.ssh("systemctl is-active aegis-verify-cmdline.service").stdout.strip() == "active"
    assert gui.ssh("findmnt -no SOURCE /").stdout.startswith("composefs:")
    denials = gui.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    (logdir / "gui-selinux-denials.txt").write_text(denials)
    assert not denials.strip(), f"SELinux denials in the graphical session:\n{denials[:3000]}"
    failed = gui.ssh("systemctl --failed --no-legend --plain").stdout.strip()
    assert not failed, failed


def test_gui_keyboard_types_into_konsole(gui, logdir):
    """Keyboard: Ctrl+Alt+T opens Konsole; text typed on the virtual keyboard runs."""
    gui.send_keys("ctrl-alt-t")
    wait_for(gui, f"pgrep -u {USER} -x konsole", 60, "Konsole to start")
    time.sleep(4)
    gui.type_text("echo AEGIS-GUI-OK > /tmp/aegis-typed\n")
    wait_for(gui, "grep -qx AEGIS-GUI-OK /tmp/aegis-typed", 30, "the typed command to run")
    owner = gui.ssh("stat -c %U /tmp/aegis-typed").stdout.strip()
    assert owner == USER
    shot(gui, logdir, "konsole")


def test_gui_file_manager_and_settings_start(gui, logdir):
    """Dolphin and System Settings start in the session and keep running."""
    for application in ("dolphin", "systemsettings"):
        launch(gui, application)
        seconds = wait_for(gui, f"pgrep -u {USER} -x {application}", 60, f"{application} to start")
        with (logdir / "gui-launch-times.txt").open("a") as times:
            times.write(f"{application}: process after {seconds:.1f} s\n")
        time.sleep(8)
        assert gui.ssh(f"pgrep -u {USER} -x {application}", check=False).returncode == 0, (
            f"{application} exited"
        )
        shot(gui, logdir, application)


def test_gui_pointer_opens_the_desktop_menu(gui, logdir):
    """Pointer: a right click on the desktop changes the screen (context menu); Esc closes it."""
    gui.send_keys("meta_l-d")  # show the desktop
    time.sleep(2)
    before = shot(gui, logdir, "before-click").read_bytes()
    gui.click(0.25, 0.25, button="right")
    time.sleep(2)
    after = shot(gui, logdir, "after-click").read_bytes()
    changed = sum(1 for a, b in zip(before, after, strict=False) if a != b)
    (logdir / "gui-pointer.txt").write_text(f"bytes changed by the right click: {changed}\n")
    gui.send_keys("esc")
    assert changed > 10000, "the right click changed nothing on the screen"


def test_gui_network_and_audio(gui, logdir):
    """Networking is connected; PipeWire offers the virtual sound card to the user."""
    assert gui.ssh("nmcli -t -f STATE general").stdout.strip().startswith("connected")
    audio = as_user(gui, "wpctl status", check=False).stdout
    (logdir / "gui-audio.txt").write_text(audio)
    sinks = audio.split("Sinks:", 1)[1].split("Sources:", 1)[0] if "Sinks:" in audio else ""
    assert re.search(r"\d+\.\s+\S", sinks), f"no audio output device:\n{audio[:2000]}"


def test_gui_resource_usage(gui, logdir, record_property):
    """Record memory, processes and startup time of the graphical session."""
    meminfo = dict(line.split(":", 1) for line in gui.ssh("cat /proc/meminfo").stdout.splitlines())
    total = int(meminfo["MemTotal"].split()[0]) // 1024
    available = int(meminfo["MemAvailable"].split()[0]) // 1024
    report = (
        f"memory in use (MiB): {total - available}\n"
        f"processes: {gui.ssh('ps -e --no-headers | wc -l').stdout.strip()}\n"
        f"user processes: {gui.ssh(f'ps -u {USER} --no-headers | wc -l').stdout.strip()}\n"
        f"startup: {gui.ssh('systemd-analyze').stdout.splitlines()[0]}\n"
        f"top user processes by memory:\n"
        f"{gui.ssh(f'ps -o rss,args -u {USER} --sort=-rss | head -n 8').stdout}"
    )
    (logdir / "gui-resources.txt").write_text(report)
    record_property("gui_memory_in_use_mib", total - available)


def test_gui_restart_returns_to_the_desktop(gui, logdir):
    """Restart: after a reboot the session comes back."""
    before = gui.ssh("cat /proc/sys/kernel/random/boot_id").stdout.strip()
    gui.ssh("systemctl reboot", check=False)
    time.sleep(10)
    gui.wait_for_ssh(240)
    assert gui.ssh("cat /proc/sys/kernel/random/boot_id").stdout.strip() != before
    wait_for_session(gui)
    time.sleep(10)
    shot(gui, logdir, "after-restart")


def test_gui_shuts_down_cleanly(gui):
    """Shutdown: power-off ends QEMU with status 0, no unit fails on the way."""
    gui.ssh("systemctl poweroff", check=False)
    assert gui.wait_for_exit(180) == 0
    serial = gui.serial_text()
    assert POWER_DOWN.search(serial)
    shutdown = serial[serial.rfind("Stopping") :] if "Stopping" in serial else serial
    last_boot = serial[serial.rfind("Linux version") :]
    assert not FAILED_UNIT.findall(last_boot[last_boot.find("Stopping") :]), shutdown[-2000:]

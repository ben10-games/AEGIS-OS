"""Live ISO: the downloadable AEGIS-OS-GUI-v2-Live.iso, checked and booted like a user would.

First the ISO file itself: checksums, the ISO 9660 volume, the El Torito UEFI boot image
and the boot menu. Then one boot in QEMU on hardware chosen to match Oracle VirtualBox's
defaults for a Linux guest with EFI (harness.qemu.VmConfig.virtualbox_like): the ISO as
a read-only SATA CD-ROM, i440FX chipset, VMware SVGA II display with 128 MB (VirtualBox's
VMSVGA uses the same guest driver, vmwgfx), PS/2 keyboard, USB tablet, Intel PRO/1000
network card, Intel HD Audio, 4 GiB of memory, 2 CPUs, OVMF without Secure Boot keys.
This is not VirtualBox itself; see VIRTUALBOX_GUIDE.md for what that leaves unverified.

The display is the one exception. QEMU's VMware SVGA II emulation does not show what a
current guest draws (CI run 45189500261: the screen kept the boot messages while the
desktop ran), so the interactive tests use QEMU's standard VGA. A second, shorter boot
with the VMware SVGA II device then checks that the desktop session starts there too
and records which kernel driver took the device.

The only thing the test adds to the machine is a throw-away SSH key for root (a systemd
credential in the firmware tables, test access only). The desktop account, its automatic
login and the administrator password come from the ISO alone.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from harness.qemu import Vm, VmConfig, find_firmware, free_local_port, generate_ssh_key

USER = "aegis"
UID = 1000
RUNTIME = f"/run/user/{UID}"
LABEL = "AEGIS_LIVE"
SSH_DEADLINE_S = 300
SESSION_DEADLINE_S = 300
ISSUE = "/etc/issue.d/50-aegis-live-admin.issue"
# Runs in the guest as the desktop user: su to root with a password typed on a terminal.
SU_CHECK = """
import sys
import pexpect
child = pexpect.spawn("su -c 'id -u' root", timeout=20)
child.expect("Password:")
child.sendline(sys.argv[1])
child.expect(pexpect.EOF)
import re
text = re.sub(r"\\x1b\\][^\\x07\\x1b]*(?:\\x07|\\x1b\\\\)|\\x1b\\[[0-9;?]*[A-Za-z]", "",
              child.before.decode())
lines = [line.strip() for line in text.splitlines() if line.strip()]
print(lines[-1] if lines else "")
"""
PASSWORD = re.compile(r"password: ([a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4})")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*command: str) -> str:
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout


@pytest.fixture(scope="module")
def extracted(iso, tmp_path_factory) -> Path:
    target = tmp_path_factory.mktemp("iso")
    run(
        "xorriso", "-osirrox", "on", "-indev", str(iso),
        "-extract", "/images/efiboot.img", str(target / "efiboot.img"),
        "-extract", "/EFI/BOOT/grub.cfg", str(target / "grub.cfg"),
        "-extract", "/EFI/BOOT/BOOTX64.EFI", str(target / "BOOTX64.EFI"),
    )  # fmt: skip
    return target


@contextlib.contextmanager
def booted(iso, workdir, logdir, accel, display: str, name: str, cpus: int = 2):
    """The ISO booted on VirtualBox-like hardware, reachable over SSH as root (test key)."""
    secrets = Path(tempfile.mkdtemp(prefix="aegis-live-key-"))
    key, public_key = generate_ssh_key(secrets)
    scratch = Path(tempfile.mkdtemp(prefix="aegis-live-", dir=workdir))
    code, vars_template = find_firmware()
    firmware_vars = scratch / f"vars{vars_template.suffix}"
    shutil.copyfile(vars_template, firmware_vars)
    cfg = VmConfig(
        disk=iso,
        firmware_code=code,
        firmware_vars=firmware_vars,
        ssh_port=free_local_port(),
        serial_log=logdir / f"{name}-serial.log",
        authorized_key=public_key,
        accel=accel,
        cpus=cpus,
        memory_mib=4096,
        qmp_socket=scratch / "qmp.sock",
        graphics=True,
        virtualbox_like=True,
        vbox_display=display,
        console_diagnostics=False,
    )
    vm = Vm(cfg, key, timeout_scale=10.0 if accel == "tcg" else 1.0)
    try:
        vm.start()
        seconds = vm.wait_for_ssh(SSH_DEADLINE_S)
        log(logdir, "timings", f"{name} ({display}): power-on to SSH: {seconds:.1f} s")
        yield vm
    finally:
        vm.kill()
        shutil.rmtree(secrets, ignore_errors=True)
        shutil.rmtree(scratch, ignore_errors=True)


@pytest.fixture(scope="module")
def live(iso, workdir, logdir, accel):
    with booted(iso, workdir, logdir, accel, "VGA", "live") as vm:
        yield vm


def as_user(vm, command: str, check: bool = True, timeout: float = 60):
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
    return vm.screenshot(logdir / f"live-{name}.ppm", fmt="ppm")


def ppm_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:64].split()
    assert header[0] == b"P6", header
    return int(header[1]), int(header[2])


def log(logdir: Path, name: str, text: str) -> None:
    with (logdir / f"live-{name}.txt").open("a") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


# --- the ISO file ------------------------------------------------------------------------


def test_release_files_and_checksums(iso, logdir):
    listed = dict(
        reversed(line.split(None, 1))
        for line in (iso.parent / "SHA256SUMS").read_text().splitlines()
        if line.strip()
    )
    assert {iso.name, "VIRTUALBOX_GUIDE.md", "CHANGELOG-GUI-v2.md", "BUILD-INFO.txt"} <= set(listed)
    for name, digest in listed.items():
        assert sha256(iso.parent / name) == digest, name
    size = iso.stat().st_size
    log(logdir, "iso", f"size: {size} bytes ({size / 2**30:.2f} GiB)")
    assert size < 4 * 2**30, "the ISO should stay below 4 GiB"


def test_iso_volume_and_uefi_boot_record(iso, logdir):
    volume = run("xorriso", "-indev", str(iso), "-pvd_info")
    torito = run("xorriso", "-indev", str(iso), "-report_el_torito", "plain")
    files = run("xorriso", "-indev", str(iso), "-find", "/", "-type", "f")
    log(logdir, "iso", volume + torito)
    assert re.search(rf"Volume Id\s*:\s*{LABEL}\b", volume), volume
    assert re.search(r"El Torito boot img\s*:\s*1\s+UEFI\s+y", torito), torito
    for required in (
        "/EFI/BOOT/BOOTX64.EFI", "/EFI/BOOT/grubx64.efi", "/EFI/BOOT/grub.cfg",
        "/images/efiboot.img", "/images/pxeboot/vmlinuz", "/images/pxeboot/initrd.img",
        "/LiveOS/squashfs.img",
    ):  # fmt: skip
        assert f"'{required}'" in files, f"{required} missing from the ISO"


def test_uefi_boot_image_and_menu(extracted, logdir):
    listing = run("mdir", "-i", str(extracted / "efiboot.img"), "-b", "::/EFI/BOOT")
    log(logdir, "iso", listing)
    for name in ("BOOTX64.EFI", "grubx64.efi", "grub.cfg"):
        assert name.lower() in listing.lower(), f"{name} missing from the EFI boot image"
    assert (extracted / "BOOTX64.EFI").read_bytes()[:2] == b"MZ", "shim is not a PE image"
    menu = (extracted / "grub.cfg").read_text()
    log(logdir, "grub", menu)
    assert f"root=live:CDLABEL={LABEL}" in menu and "rd.live.image" in menu
    assert "set timeout=5" in menu and "set default=0" in menu
    for weakening in ("enforcing=0", "selinux=0", "autorelabel", "lockdown=none"):
        assert weakening not in menu, f"the boot menu weakens a control: {weakening}"
    assert "lockdown=integrity" in menu, "the AEGIS kernel arguments are missing"


# --- one boot on VirtualBox-like hardware -------------------------------------------------


def test_boots_as_a_live_system(live, logdir):
    cmdline = live.ssh("cat /proc/cmdline").stdout
    log(logdir, "boot", f"cmdline: {cmdline}")
    assert "rd.live.image" in cmdline and f"root=live:CDLABEL={LABEL}" in cmdline
    root = live.ssh("findmnt -no SOURCE,FSTYPE /").stdout.split()
    log(logdir, "boot", f"root: {root}")
    assert root[-1] == "overlay", root
    release = live.ssh("cat /usr/lib/os-release").stdout
    assert "IMAGE_ID=aegis-gui-live" in release, release
    assert live.ssh("cat /sys/kernel/security/lockdown").stdout.count("[integrity]") == 1
    assert live.ssh("findmnt -rn -o FSTYPE /run/rootfsbase").stdout.strip() == "squashfs"
    # The writable part of the overlay may use up to 75% of the memory
    # (aegis-live-overlay-space.service), not systemd's default 20%.
    memory = int(live.ssh("awk '/^MemTotal:/ {print $2}' /proc/meminfo").stdout) * 1024
    size = int(live.ssh("df -B1 --output=size / | tail -n 1").stdout)
    log(logdir, "boot", f"writable overlay: {size} bytes of {memory} bytes memory")
    assert 0.70 * memory <= size <= 0.80 * memory, (size, memory)


def test_selinux_enforcing_with_labelled_files(live, logdir):
    assert live.ssh("getenforce").stdout.strip() == "Enforcing"
    contexts = live.ssh("stat -c '%n %C' /usr/bin/bash /etc/shadow /usr/bin/sddm").stdout
    log(logdir, "boot", contexts)
    assert ":shell_exec_t:" in contexts and ":shadow_t:" in contexts and ":xdm_exec_t:" in contexts


def test_unprivileged_account_logs_in_automatically(live, logdir, record_property):
    seconds = wait_for(
        live,
        f"pgrep -u {USER} -x plasmashell && pgrep -u {USER} -x kwin_wayland",
        SESSION_DEADLINE_S,
        "a Plasma Wayland session for the live account",
    )
    record_property("seconds_from_ssh_to_session", round(seconds, 1))
    log(logdir, "timings", f"SSH to Plasma session: {seconds:.1f} s")
    assert live.ssh(f"id -u {USER}").stdout.strip() == str(UID)
    groups = live.ssh(f"id -nG {USER}").stdout.split()
    log(logdir, "account", f"groups: {groups}")
    assert "wheel" not in groups
    assert live.ssh(f"passwd -S {USER}").stdout.split()[1] == "L", "the live account has a password"
    assert live.ssh(f"runuser -u {USER} -- sudo -n true", check=False).returncode != 0
    session = live.ssh(
        f"loginctl list-sessions --no-legend | awk '$3 == \"{USER}\" {{print $1}}'"
    ).stdout.split()[0]
    assert live.ssh(f"loginctl show-session {session} -p Type --value").stdout.strip() == "wayland"
    time.sleep(25)  # let the desktop finish drawing and the login helpers run
    shot(live, logdir, "desktop")


DRM = (
    "for c in /sys/class/drm/card*; do [ -e $c/device ] || continue; "
    "echo $(basename $c) $(basename $(readlink -f $c/device/driver) 2>/dev/null); done; "
    "dmesg | grep -iE 'vmwgfx|bochs|simpledrm|efifb|drm' | tail -n 30"
)


def test_display_driver_and_size(live, logdir):
    drm = live.ssh(DRM, check=False).stdout
    outputs = as_user(live, "kscreen-doctor --outputs", check=False).stdout
    log(logdir, "display", f"{drm}\n{outputs}")
    assert "bochs" in drm, f"QEMU's standard VGA is not driven by bochs-drm:\n{drm}"
    width, height = ppm_size(shot(live, logdir, "resolution"))
    log(logdir, "display", f"screen: {width}x{height}")
    assert (width, height) == (1920, 1080), f"screen is {width}x{height}"


def test_keyboard_types_into_konsole(live, logdir):
    live.send_keys("ctrl-alt-t")
    wait_for(live, f"pgrep -u {USER} -x konsole", 60, "Konsole to start")
    time.sleep(4)
    live.type_text("echo AEGIS-LIVE-OK > /tmp/aegis-live-typed\n")
    wait_for(live, "grep -qx AEGIS-LIVE-OK /tmp/aegis-live-typed", 30, "the typed command")
    assert live.ssh("stat -c %U /tmp/aegis-live-typed").stdout.strip() == USER
    shot(live, logdir, "konsole")


def test_pointer_opens_the_desktop_menu(live, logdir):
    live.send_keys("meta_l-d")
    time.sleep(2)
    before = shot(live, logdir, "before-click").read_bytes()
    live.click(0.25, 0.25, button="right")
    time.sleep(2)
    after = shot(live, logdir, "after-click").read_bytes()
    changed = sum(1 for a, b in zip(before, after, strict=False) if a != b)
    log(logdir, "pointer", f"bytes changed by the right click: {changed}")
    live.send_keys("esc")
    assert changed > 10000, "the right click changed nothing on the screen"


def test_file_manager_and_settings_start(live, logdir):
    for application in ("dolphin", "systemsettings"):
        as_user(live, f"systemd-run --user --collect --unit=aegis-test-{application} {application}")
        seconds = wait_for(live, f"pgrep -u {USER} -x {application}", 60, f"{application}")
        log(logdir, "timings", f"{application}: process after {seconds:.1f} s")
        time.sleep(8)
        assert live.ssh(f"pgrep -u {USER} -x {application}", check=False).returncode == 0
        shot(live, logdir, application)


def test_security_dashboard_reports_the_live_state(live, logdir):
    facts = dict(
        line.split("=", 1)
        for line in as_user(live, "/usr/libexec/aegis/security-status").stdout.splitlines()
        if "=" in line
    )
    log(logdir, "security-status", "\n".join(f"{k}={v}" for k, v in facts.items()))
    assert facts["live"] == "yes"
    assert facts["selinux"] == "Enforcing"
    assert facts["root"] == "live-overlay"
    assert facts["root_digest"] == "none"
    assert facts["cmdline_check"] == "not-applicable-live"
    assert facts["secureboot"] == "disabled"
    assert facts["firewall"] == "active"
    assert facts["lockdown"] == "integrity"
    assert facts["deployment"].startswith("aegis-gui-live ")
    as_user(
        live,
        "systemd-run --user --collect --unit=aegis-test-dashboard "
        "plasmawindowed org.aegisos.security",
    )
    wait_for(live, f"pgrep -u {USER} -x plasmawindowed", 60, "the security widget window")
    time.sleep(10)
    shot(live, logdir, "security-dashboard")
    errors = as_user(
        live,
        'journalctl --user -b -o cat | grep -iE "aegisos|org/aegisos" '
        '| grep -iE "error|cannot|not installed|failed" || true',
    ).stdout
    log(logdir, "qml-errors", errors or "none")
    assert not errors.strip(), errors[:3000]
    live.ssh(f"pkill -u {USER} -x plasmawindowed", check=False)


def test_network_and_audio(live, logdir):
    drivers = live.ssh(
        "for n in /sys/class/net/*/device/driver; do basename $(readlink $n); done"
    ).stdout.split()
    state = live.ssh("nmcli -t -f STATE general").stdout.strip()
    audio = as_user(live, "wpctl status", check=False).stdout
    log(logdir, "network-audio", f"network drivers: {drivers}\nstate: {state}\n{audio}")
    assert "e1000" in drivers
    assert state.startswith("connected"), state
    sinks = audio.split("Sinks:", 1)[1].split("Sources:", 1)[0] if "Sinks:" in audio else ""
    assert re.search(r"\d+\.\s+\S", sinks), f"no audio output device:\n{audio[:2000]}"


def test_administrator_password_is_per_boot_and_console_only(live, logdir):
    """root gets a random password at boot, shown only on the text consoles (agetty's
    issue text, readable by root only); the desktop account cannot read it; su accepts
    it and refuses a wrong one. The password itself is not written to the logs."""
    mode = live.ssh(f"stat -c '%a %U' {ISSUE}").stdout.strip()
    assert mode == "600 root", mode
    match = PASSWORD.search(live.ssh(f"cat {ISSUE}").stdout)
    assert match, "no password in the console text"
    password = match.group(1)
    assert live.ssh(f"runuser -u {USER} -- cat {ISSUE}", check=False).returncode != 0
    assert live.ssh("passwd -S root").stdout.split()[1] == "P"
    script = base64.b64encode(SU_CHECK.encode()).decode()
    live.ssh(f"echo {script} | base64 -d > /tmp/aegis-su-check.py")
    good = live.ssh(
        f"runuser -u {USER} -- python3 /tmp/aegis-su-check.py '{password}'", check=False
    )
    bad = live.ssh(f"runuser -u {USER} -- python3 /tmp/aegis-su-check.py wrong-pass", check=False)
    log(logdir, "account", f"su with the console password: {good.stdout.strip()[-40:]}")
    log(logdir, "account", f"su with a wrong password: {bad.stdout.strip()[-60:]}")
    assert good.stdout.strip() == "0", good.stdout + good.stderr
    assert bad.stdout.strip() != "0", bad.stdout
    assert live.ssh("grep -c . /etc/sudoers.d/* 2>/dev/null || true").stdout.strip() in ("", "0")


# --- GUI v2: renderer, glass profiles, performance, launcher, resolutions -------------

GLASS = "/usr/libexec/aegis/glass-profile"
PROFILE_ORDER = ("performance", "balanced", "full")


def effect_loaded(vm, effect: str) -> bool:
    reply = as_user(
        vm,
        f"busctl --user call org.kde.KWin /Effects org.kde.kwin.Effects isEffectLoaded s {effect}",
        check=False,
    ).stdout.strip()
    return reply == "b true"


BLUR_DIAGNOSTICS = r"""
echo "blurEnabled=$(kreadconfig6 --file kwinrc --group Plugins --key blurEnabled)"
ls -l "$HOME/.config/kwinrc"
grep -A4 '^\[Plugins\]' "$HOME/.config/kwinrc"
busctl --user get-property org.kde.KWin /Effects org.kde.kwin.Effects loadedEffects
tr '\0' '\n' < "/proc/$(pgrep -u "$(id -u)" -x kwin_wayland)/environ" \
  | grep -E '^(XDG_CONFIG|KDE|HOME=)' || true
"""


def blur_diagnostics(vm) -> str:
    """Why KWin has blur loaded or not: the user's setting, KWin's effects and the
    configuration paths in KWin's environment (live-iso runs 45822043527, 45823218002:
    blur stayed loaded under Performance Glass on the renewed base)."""
    script = base64.b64encode(BLUR_DIAGNOSTICS.encode()).decode()
    return (
        as_user(vm, f"echo {script} | base64 -d | sh", check=False).stdout
        + vm.ssh(
            "journalctl -b -o cat --no-pager | grep -i blur | tail -n 15 || true", check=False
        ).stdout
    )


def assert_blur(vm, logdir, wanted: bool, label: str) -> None:
    if effect_loaded(vm, "blur") != wanted:
        log(logdir, "blur-diagnostics", f"{label}: blur loaded, wanted {wanted}\n")
        log(logdir, "blur-diagnostics", blur_diagnostics(vm))
        raise AssertionError(f"{label}: blur loaded is not {wanted} (see blur-diagnostics)")


def cpu_ticks(vm, names: tuple[str, ...]) -> dict[str, int]:
    """Summed user+system clock ticks of the live user's processes with these names."""
    script = (
        "for n in " + " ".join(names) + "; do t=0; "
        f"for p in $(pgrep -u {USER} -x $n); do "
        "t=$((t + $(awk '{print $14 + $15}' /proc/$p/stat))); done; echo $n $t; done; "
        "awk '/^cpu / {print \"total\", $2+$3+$4+$5+$6+$7+$8}' /proc/stat"
    )
    return {k: int(v) for k, v in (line.split() for line in vm.ssh(script).stdout.splitlines())}


def frame_meter(vm, logdir: Path, label: str, launcher: bool = False) -> str:
    """Run the AEGIS frame meter for one measurement; returns its AEGIS-FRAMES line and logs
    the CPU share of the compositor, the shell and the meter while it ran. With launcher,
    the launcher popup is opened over the animation during the measurement, so KWin has
    to blur changing content behind a glass surface on every frame (where blur is on)."""
    since = vm.ssh("date '+%Y-%m-%d %H:%M:%S'").stdout.strip()
    names = ("kwin_wayland", "plasmashell", "plasmawindowed")
    before = cpu_ticks(vm, names)
    as_user(
        vm,
        f"systemd-run --user --collect --unit=aegis-meter-{label} plasmawindowed "
        "org.aegisos.framemeter",
    )
    if launcher:
        time.sleep(2)
        sw, sh, x, y, w, h = dock_geometry(vm)
        vm.click((x + h / 2) / sw, (y + h / 2) / sh)
    line = ""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not line:
        time.sleep(2)
        out = as_user(vm, f'journalctl --user --since "{since}" -o cat', check=False).stdout
        line = next((x for x in out.splitlines() if "AEGIS-FRAMES" in x), "")
    after = cpu_ticks(vm, names)
    shot(vm, logdir, f"meter-{label}")
    if launcher:
        vm.send_keys("esc")
    as_user(vm, f"systemctl --user stop aegis-meter-{label}.service", check=False)
    cpus = int(vm.ssh("nproc").stdout)
    span = max(1, after["total"] - before["total"])
    shares = " ".join(f"{n}={100.0 * cpus * (after[n] - before[n]) / span:.0f}%" for n in names)
    log(logdir, "performance", f"{label}: {line.split('AEGIS-FRAMES ')[-1] or 'no result'}")
    log(logdir, "performance", f"{label}: CPU while measuring (100% = one CPU): {shares}")
    return line


def test_renderer_identified_and_auto_profile(live, logdir):
    """GPU renderer identification and the automatic profile: Performance Glass on a
    software renderer, Balanced Glass on a hardware one."""
    report = as_user(live, "/usr/libexec/aegis/graphics-report", check=False).stdout
    log(logdir, "renderer", report)
    facts = dict(line.split("=", 1) for line in report.splitlines() if "=" in line)
    assert facts.get("renderer"), report
    assert "kwin: Compositing Type: OpenGL" in report, report
    expected = "performance" if facts["renderer_class"] == "software" else "balanced"
    assert facts["choice"] == "auto", report
    assert facts["effective"] == expected, report
    assert_blur(live, logdir, expected != "performance", f"auto ({expected})")


def test_glass_profiles_switch_and_measure(live, logdir, record_property):
    """Each profile changes what KWin runs (blur loaded or not, animation length), and the
    frame meter measures frames and CPU under each. Numbers are recorded, not asserted:
    they describe QEMU with software rendering on a CI runner."""
    results = {}
    for profile in PROFILE_ORDER:
        out = as_user(live, f"{GLASS} apply {profile}").stdout
        assert f"effective={profile}" in out, out
        time.sleep(4)
        assert_blur(live, logdir, profile != "performance", profile)
        factor = as_user(
            live, "kreadconfig6 --file kdeglobals --group KDE --key AnimationDurationFactor"
        ).stdout.strip()
        assert factor == {"full": "1", "balanced": "0.75", "performance": "0.5"}[profile]
        line = frame_meter(live, logdir, profile)
        assert "fps=" in line, f"the frame meter reported nothing for {profile}"
        results[profile] = float(line.split("fps=")[1].split()[0])
        record_property(f"fps_{profile}", results[profile])
        line = frame_meter(live, logdir, f"{profile}-glass-popup", launcher=True)
        assert "fps=" in line, f"the frame meter reported nothing for {profile} (popup)"
        results[f"{profile}-glass-popup"] = float(line.split("fps=")[1].split()[0])
        record_property(f"fps_{profile}_glass_popup", results[f"{profile}-glass-popup"])
        time.sleep(3)
        shot(live, logdir, f"glass-{profile}")
    as_user(live, f"{GLASS} apply auto")
    log(logdir, "performance", f"frames per second by profile: {results}")


def in_session(vm, command: str, check: bool = True):
    """Run a command through the user's systemd manager, with the desktop session's
    environment (kscreen-doctor aborts when started outside it: CI run 45601312768)."""
    return as_user(vm, f"systemd-run --user --wait --pipe --quiet {command}", check=check)


def show_desktop(vm, showing: bool) -> None:
    as_user(
        vm,
        f"busctl --user call org.kde.KWin /KWin org.kde.KWin showDesktop b {str(showing).lower()}",
        check=False,
    )


def test_launcher_opens_with_search(live, logdir):
    """The AEGIS launcher (Application Dashboard) opens with a click on the AEGIS mark at
    the left end of the dock, finds an application by typing, and closes with Escape."""
    show_desktop(live, True)
    time.sleep(3)
    sw, sh, x, y, w, h = dock_geometry(live)
    before = shot(live, logdir, "before-launcher").read_bytes()
    live.click((x + h / 2) / sw, (y + h / 2) / sh)
    time.sleep(3)
    opened = shot(live, logdir, "launcher").read_bytes()
    live.type_text("konsole")
    time.sleep(2)
    shot(live, logdir, "launcher-search")
    live.send_keys("esc")
    time.sleep(1)
    live.send_keys("esc")
    time.sleep(1)
    show_desktop(live, False)
    changed = sum(1 for a, b in zip(before, opened, strict=False) if a != b)
    log(logdir, "launcher", f"bytes changed by opening the launcher: {changed}")
    assert changed > 100000, "the launcher did not open"


DOCK_SCRIPT = """
const s = workspace.virtualScreenSize;
for (const w of workspace.windowList()) {
    if (w.dock) {
        const g = w.frameGeometry;
        console.info("AEGIS-DOCK " + s.width + " " + s.height + " " + Math.round(g.x) + " "
            + Math.round(g.y) + " " + Math.round(g.width) + " " + Math.round(g.height));
    }
}
"""


def dock_geometry(vm) -> tuple[int, ...]:
    """Screen size and dock geometry, asked from KWin through a short KWin script."""
    script = base64.b64encode(DOCK_SCRIPT.encode()).decode()
    vm.ssh(f"echo {script} | base64 -d > /tmp/aegis-dock.js && chmod 0644 /tmp/aegis-dock.js")
    since = vm.ssh("date '+%Y-%m-%d %H:%M:%S'").stdout.strip()
    as_user(
        vm,
        "busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting unloadScript s "
        "aegisdock",
        check=False,
    )
    loaded = as_user(
        vm,
        "busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting loadScript ss "
        "/tmp/aegis-dock.js aegisdock",
    ).stdout.split()
    as_user(
        vm, f"busctl --user call org.kde.KWin /Scripting/Script{loaded[-1]} org.kde.kwin.Script run"
    )
    for _ in range(10):
        time.sleep(1)
        out = as_user(vm, f'journalctl --user --since "{since}" -o cat', check=False).stdout
        lines = [x for x in out.splitlines() if "AEGIS-DOCK" in x]
        if lines:
            return tuple(int(v) for v in lines[-1].split("AEGIS-DOCK ")[1].split())
    raise AssertionError("KWin reported no dock window")


def offered_modes(text: str) -> tuple[str, list[tuple[str, int, int, float]]]:
    """Output name and its modes (id, width, height, refresh) from 'kscreen-doctor
    --outputs' (the '--json' variant aborted outside the session in CI run 45597365211)."""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    name = re.search(r"^Output:\s+\d+\s+(\S+)", text, re.M)
    modes = [
        (m[0], int(m[1]), int(m[2]), float(m[3]))
        for m in re.findall(r"(\d+):(\d+)x(\d+)@([\d.]+)", text)
    ]
    return (name.group(1) if name else "none"), modes


def corner_is_drawn(path: Path) -> bool:
    """True if the bottom-right 16x16 pixels of a PPM screenshot are not pure black."""
    data = path.read_bytes()
    fields = data[:64].split()
    width, height = int(fields[1]), int(fields[2])
    offset = len(data) - width * height * 3
    for y in range(height - 16, height):
        row = data[offset + (y * width + width - 16) * 3 : offset + (y * width + width) * 3]
        if max(row) > 4:
            return True
    return False


@pytest.mark.parametrize("size", ["1366x768", "largest", "1920x1080"])
def test_resolution_change_keeps_the_dock_in_place(live, logdir, size):
    """Display resizing: the output changes to SIZE (as when a VirtualBox window is resized
    or made full screen), the desktop fills the whole screen, and Plasma moves the dock to
    the bottom centre of the new size. "largest" is the largest mode the virtual card
    offers (QEMU's standard VGA offers no 2560x1440: CI run 45604938784)."""
    output, modes = offered_modes(in_session(live, "kscreen-doctor --outputs").stdout)
    sizes = sorted({(w, h) for _, w, h, _ in modes}, key=lambda s: -s[0] * s[1])
    listing = " ".join(f"{w}x{h}" for w, h in sizes)
    log(logdir, "resolutions", f"{size}: offered by {output}: {listing}")
    if size == "largest":
        chosen = max(modes, key=lambda m: (m[1] * m[2], m[3]))
    else:
        width, height = (int(v) for v in size.split("x"))
        matching = sorted(
            (m for m in modes if (m[1], m[2]) == (width, height)), key=lambda m: -m[3]
        )
        assert matching, f"{size} is not offered"
        chosen = matching[0]
    mode_id, width, height, _ = chosen
    in_session(live, f"kscreen-doctor output.{output}.mode.{mode_id}")
    time.sleep(6)
    show_desktop(live, True)
    time.sleep(3)
    path = shot(live, logdir, f"res-{size}")
    shot_w, shot_h = ppm_size(path)
    # A mode's framebuffer width can be rounded down to a multiple of 8 (1366 -> 1360).
    assert width - 8 < shot_w <= width and shot_h == height, (shot_w, shot_h, width, height)
    assert corner_is_drawn(path), "black area at the bottom-right corner"
    sw, sh, x, y, w, h = dock_geometry(live)
    log(
        logdir,
        "resolutions",
        f"{size} ({width}x{height}): screen {sw}x{sh}, dock at {x},{y} size {w}x{h}",
    )
    # KWin's screen is the mode; QEMU's standard VGA stores lines in multiples of 8 pixels,
    # so its framebuffer (the screenshot) can be up to 7 pixels narrower (1366 -> 1360,
    # CI run 45608395419). VirtualBox's VMSVGA has no such limit.
    assert (sw, sh) == (width, height)
    assert abs((x + w / 2) - sw / 2) <= 4, "dock is not centred"
    assert sh - 40 <= y + h <= sh, "dock is not at the bottom"
    assert x >= 0 and x + w <= sw


def test_virtualbox_guest_tools_present_and_idle_outside_virtualbox(live, logdir):
    """Fedora's VirtualBox guest tools are installed; under QEMU their services are skipped
    by their own condition (VirtualBox only), not failed."""
    files = live.ssh("rpm -ql virtualbox-guest-additions | grep -E 'bin/|\\.service$'").stdout
    units = live.ssh(
        "for u in $(rpm -ql virtualbox-guest-additions | grep -E '\\.service$' "
        "| xargs -r -n1 basename); do echo $u $(systemctl is-enabled $u) "
        "$(systemctl show -p ConditionResult --value $u) $(systemctl is-failed $u); done",
        check=False,
    ).stdout
    log(logdir, "virtualbox", f"{files}\nunits (enabled, condition met, failed):\n{units}")
    assert "VBoxClient" in files and "VBoxService" in files, files
    assert "failed" not in units.split(), units


def test_idle_resource_usage(live, logdir, record_property):
    show_desktop(live, True)
    time.sleep(10)
    names = ("kwin_wayland", "plasmashell")
    before = cpu_ticks(live, names)
    time.sleep(20)
    after = cpu_ticks(live, names)
    cpus = int(live.ssh("nproc").stdout)
    span = max(1, after["total"] - before["total"])
    shares = {n: round(100.0 * cpus * (after[n] - before[n]) / span, 1) for n in names}
    memory = live.ssh("free -m | awk '/^Mem:/ {print $3, $7}'").stdout.split()
    log(
        logdir,
        "performance",
        f"idle (20 s, desktop shown): CPU {shares} (100% = one CPU); memory used "
        f"{memory[0]} MiB, available {memory[1]} MiB",
    )
    record_property("idle_kwin_cpu_percent", shares["kwin_wayland"])
    record_property("idle_memory_used_mib", int(memory[0]))


def test_no_failed_units_or_denials(live, logdir):
    failed = live.ssh("systemctl --failed --no-legend --plain").stdout.strip()
    denials = live.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    log(logdir, "failed-units", failed or "none")
    log(logdir, "selinux-denials", denials or "none")
    assert not failed, failed
    assert not denials.strip(), denials[:3000]


def test_shuts_down_cleanly(live, logdir):
    live.ssh("systemctl poweroff", check=False)
    status = live.wait_for_exit(180)
    assert status == 0, f"QEMU did not exit cleanly after power-off (status {status})"
    assert "reboot: Power down" in live.serial_text()


def test_desktop_session_with_the_vmware_svga_device(iso, workdir, logdir, accel):
    """Second boot with VMSVGA's device model: the session starts; the driver is recorded.
    The screen content is not checked (QEMU's emulation does not show it)."""
    with booted(iso, workdir, logdir, accel, "vmware-svga", "live-vmsvga") as vm:
        seconds = wait_for(
            vm,
            f"pgrep -u {USER} -x plasmashell && pgrep -u {USER} -x kwin_wayland",
            SESSION_DEADLINE_S,
            "a Plasma Wayland session with the VMware SVGA II device",
        )
        time.sleep(15)
        drm = vm.ssh(DRM, check=False).stdout
        outputs = as_user(vm, "kscreen-doctor --outputs", check=False).stdout
        failed = vm.ssh("systemctl --failed --no-legend --plain").stdout.strip()
        log(logdir, "vmsvga", f"session after {seconds:.1f} s\n{drm}\n{outputs}\nfailed: {failed}")
        assert vm.ssh(f"pgrep -u {USER} -x kwin_wayland", check=False).returncode == 0
        assert not failed, failed

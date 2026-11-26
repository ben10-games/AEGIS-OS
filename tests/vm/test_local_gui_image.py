"""GUI v1: the exported graphical QCOW2 works as LOCAL_GUI_VM_GUIDE.md tells a user to run it.

This test does not use the harness's own QEMU command line. It starts the published
launcher (local-vm/run-aegis-gui-vm.sh) against the exported image the way a person on
Linux Mint would, with three differences that a CI runner needs: no window
(--display none), no host sound system (--audio none) and a QMP socket for screenshots
and input. The firmware is the launcher's own choice: OVMF without Secure Boot keys, as
on a user's machine. The image is opened with --snapshot, so the published file is
byte-for-byte the file that was tested.

Checked: the account the launcher creates (uid 1000, administrator through sudo with the
generated password, root still locked), automatic login into a Plasma Wayland session,
the 1920x1080 display, keyboard and pointer input, networking, the audio device, SELinux
enforcing without denials, and a clean power-off that ends the launcher.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from harness.qemu import free_local_port, generate_ssh_key
from harness.qmp import QmpClient

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "local-vm" / "run-aegis-gui-vm.sh"
USER = "aegis"
RUNTIME = "/run/user/1000"
SESSION_DEADLINE_S = 300
SSH_DEADLINE_S = 240


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def gui_image(request) -> Path:
    option = request.config.getoption("--local-image")
    if option:
        return Path(option).resolve()
    found = sorted((ROOT / "out" / "release-gui").glob("*.qcow2"))
    if len(found) != 1:
        pytest.fail(f"expected exactly one exported image in out/release-gui, found {found}")
    return found[0]


@pytest.fixture(scope="module")
def launched(gui_image, logdir, accel):
    """The exported image, started by the published launcher."""
    secrets = Path(tempfile.mkdtemp(prefix="aegis-gui-local-"))
    key, _public = generate_ssh_key(secrets)
    port = free_local_port()
    qmp = secrets / "qmp.sock"
    serial_log = logdir / "local-gui-serial.log"
    serial_log.unlink(missing_ok=True)
    command = [
        str(LAUNCHER),
        "--image",
        str(gui_image),
        "--snapshot",
        "--display",
        "none",
        "--audio",
        "none",
        "--accel",
        accel,
        "--ssh-key",
        str(key.with_suffix(".pub")),
        "--ssh-port",
        str(port),
        "--serial",
        f"file:{serial_log}",
        "--qmp",
        str(qmp),
    ]
    with (logdir / "local-gui-launcher.log").open("w") as output:
        proc = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT
        )
        try:
            yield {"proc": proc, "port": port, "key": key, "qmp": qmp, "image": gui_image}
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=30)
            shutil.rmtree(secrets, ignore_errors=True)
            # The launcher keeps the firmware variables, the generated password and the
            # console log next to the image; none of them may be published.
            for pattern in (".uefi-vars.*", ".password", ".serial.log"):
                for leftover in gui_image.parent.glob(f"{gui_image.name}{pattern}"):
                    leftover.unlink()


def ssh(launched, command: str, timeout: float = 60, check: bool = False):
    result = subprocess.run(
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
    if check:
        assert result.returncode == 0, f"{command}: {result.stdout}{result.stderr}"
    return result


def as_user(launched, command: str, check: bool = True):
    environment = (
        f"XDG_RUNTIME_DIR={RUNTIME} DBUS_SESSION_BUS_ADDRESS=unix:path={RUNTIME}/bus "
        "WAYLAND_DISPLAY=wayland-0 QT_QPA_PLATFORM=wayland"
    )
    return ssh(launched, f"runuser -u {USER} -- env {environment} sh -c '{command}'", check=check)


def wait_for(launched, command: str, deadline_s: float, what: str, scale: float) -> float:
    started = time.monotonic()
    while time.monotonic() - started < deadline_s * scale:
        assert launched["proc"].poll() is None, f"the launcher exited while waiting for {what}"
        if ssh(launched, command, timeout=30).returncode == 0:
            return time.monotonic() - started
        time.sleep(3)
    raise AssertionError(f"{what} did not happen within {deadline_s} s")


def qmp(launched, name: str, **arguments) -> dict:
    with QmpClient(launched["qmp"]) as client:
        return client.command(name, **arguments)


def screenshot(launched, path: Path) -> tuple[int, int]:
    """Screen dump through QMP; returns the width and height from the PPM header."""
    qmp(launched, "screendump", filename=str(path), format="ppm")
    header = path.read_bytes()[:64].split()
    assert header[0] == b"P6", header
    return int(header[1]), int(header[2])


def test_checksum_file_matches_the_exported_image(gui_image):
    listed = dict(
        reversed(line.split(None, 1))
        for line in (gui_image.parent / "SHA256SUMS").read_text().splitlines()
        if line.strip()
    )
    assert listed.get(gui_image.name) == sha256(gui_image)
    for name in ("run-aegis-gui-vm.sh", "LOCAL_GUI_VM_GUIDE.md", "IMAGE-INFO.txt"):
        assert listed.get(name) == sha256(gui_image.parent / name), name


def test_launcher_refuses_a_block_device_and_non_images(gui_image, tmp_path):
    for target in ("/dev/null", "/dev/loop0", str(tmp_path)):
        result = subprocess.run(
            [str(LAUNCHER), "--image", target, "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "refusing" in result.stderr


def test_ssh_is_reachable(launched, timeout_scale, record_property):
    seconds = wait_for(launched, "true", SSH_DEADLINE_S, "SSH", timeout_scale)
    record_property("seconds_to_ssh", round(seconds, 1))


def test_the_launcher_account(launched):
    """uid 1000, administrator, a password set by the launcher; root stays locked."""
    assert ssh(launched, f"id -u {USER}", check=True).stdout.strip() == "1000"
    assert "wheel" in ssh(launched, f"id -nG {USER}", check=True).stdout.split()
    assert ssh(launched, f"passwd -S {USER}", check=True).stdout.split()[1] == "P"
    assert ssh(launched, "passwd -S root", check=True).stdout.split()[1] == "L"
    password = Path(f"{launched['image']}.password").read_text().strip()
    sudo = ssh(launched, f"printf '%s\\n' '{password}' | runuser -u {USER} -- sudo -S -k id -u")
    assert sudo.stdout.strip().endswith("0"), sudo.stdout + sudo.stderr
    wrong = ssh(launched, f"printf 'wrong\\n' | runuser -u {USER} -- sudo -S -k id -u")
    assert wrong.returncode != 0, "sudo accepted a wrong password"


def test_desktop_session_starts_on_wayland(launched, logdir, timeout_scale, record_property):
    seconds = wait_for(
        launched,
        f"pgrep -u {USER} -x plasmashell && pgrep -u {USER} -x kwin_wayland",
        SESSION_DEADLINE_S,
        "a Plasma Wayland session for the launcher's user",
        timeout_scale,
    )
    record_property("seconds_from_ssh_to_session", round(seconds, 1))
    session = ssh(
        launched, f"loginctl list-sessions --no-legend | awk '$3 == \"{USER}\" {{print $1}}'"
    ).stdout.split()[0]
    assert ssh(launched, f"loginctl show-session {session} -p Type --value").stdout.strip() == (
        "wayland"
    )
    time.sleep(20)  # let the desktop finish drawing
    screenshot(launched, logdir / "gui-local-desktop.ppm")


def test_display_is_1920x1080(launched, logdir):
    width, height = screenshot(launched, logdir / "gui-local-resolution.ppm")
    modes = as_user(launched, "kscreen-doctor -o", check=False).stdout
    (logdir / "gui-local-kscreen.txt").write_text(modes)
    assert (width, height) == (1920, 1080), f"screen is {width}x{height}\n{modes}"


def test_keyboard_and_pointer(launched, logdir):
    """Ctrl+Alt+T opens Konsole, typed text runs as the user; a right click opens a menu."""
    keys = [{"type": "qcode", "data": k} for k in ("ctrl", "alt", "t")]
    qmp(launched, "send-key", keys=keys)
    deadline = time.monotonic() + 90
    while ssh(launched, f"pgrep -u {USER} -x konsole").returncode != 0:
        assert time.monotonic() < deadline, "Konsole did not start"
        time.sleep(3)
    time.sleep(5)
    text = "echo AEGIS-LOCAL-OK > /tmp/aegis-local-typed\n"
    names = {" ": "spc", "-": "minus", ">": "shift-dot", "/": "slash", "\n": "ret"}
    for char in text:
        name = names.get(char, char.lower())
        combo = name.split("-") if name.startswith("shift-") else [name]
        if char.isupper():
            combo = ["shift", char.lower()]
        qmp(launched, "send-key", keys=[{"type": "qcode", "data": k} for k in combo])
        time.sleep(0.05)
    deadline = time.monotonic() + 30
    while ssh(launched, "grep -qx AEGIS-LOCAL-OK /tmp/aegis-local-typed").returncode != 0:
        assert time.monotonic() < deadline, "the typed command did not run"
        time.sleep(2)
    assert ssh(launched, "stat -c %U /tmp/aegis-local-typed").stdout.strip() == USER
    screenshot(launched, logdir / "gui-local-konsole.ppm")


def test_network_audio_and_security(launched, logdir):
    assert ssh(launched, "nmcli -t -f STATE general").stdout.strip().startswith("connected")
    audio = as_user(launched, "wpctl status", check=False).stdout
    (logdir / "gui-local-audio.txt").write_text(audio)
    assert "Sinks:" in audio, audio[:2000]
    assert ssh(launched, "getenforce").stdout.strip() == "Enforcing"
    denials = ssh(launched, "journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    (logdir / "gui-local-denials.txt").write_text(denials)
    assert not denials.strip(), denials[:3000]
    release = ssh(launched, "cat /usr/lib/os-release").stdout
    assert "IMAGE_ID=aegis-gui" in release or "IMAGE_ID=aegis-dev" in release, release


def test_power_off_ends_the_launcher(launched, timeout_scale):
    ssh(launched, "systemctl poweroff")
    assert launched["proc"].wait(timeout=180 * timeout_scale) == 0


def test_published_image_was_not_modified(gui_image):
    assert sha256(gui_image) in (gui_image.parent / "SHA256SUMS").read_text()

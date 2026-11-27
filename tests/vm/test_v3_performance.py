"""AEGIS OS v3 (M13): measured performance of the persistent VDI on VirtualBox-like
hardware (QEMU with KVM on a GitHub runner, 2 CPUs, 4 GiB, software rendering; not
VirtualBox). Numbers are recorded in the report; only gross regression limits are
asserted, so that a measurement is never presented as a target that was met.
"""

from __future__ import annotations

import base64
import json
import time

import pytest
from test_v3_apps import CREATE
from test_v3_desktop import kwin
from test_v3_vdi import (
    FULL_NAME,
    PASSWORD,
    USER,
    as_user,
    log,
    log_in_at_greeter,
    vdi,  # noqa: F401  (fixture)
    vdi_machine,
    wait_for,
)


@pytest.fixture(scope="module")
def vm(vdi, workdir, logdir, accel):  # noqa: F811
    with vdi_machine(vdi, workdir, logdir, accel, "v3-performance", cpus=2) as machine:
        yield machine


def ticks(vm, names: tuple[str, ...]) -> dict[str, int]:
    script = (
        "for n in " + " ".join(names) + "; do t=0; "
        f"for p in $(pgrep -u {USER} -x $n); do "
        "set -- $(cut -d' ' -f14,15 /proc/$p/stat); t=$((t+$1+$2)); done; echo $n $t; done"
    )
    out = vm.ssh(script, check=False).stdout.split()
    return {out[i]: int(out[i + 1]) for i in range(0, len(out) - 1, 2)}


def test_boot_and_login_times(vm, logdir, record_property):
    started = time.monotonic()
    vm.start()
    vm.wait_for_ssh(300)
    wait_for(vm, "pgrep -u aegis-setup -x aegis-setup", 240, "AEGIS Setup")
    to_setup = time.monotonic() - started
    request = json.dumps(
        {"full_name": FULL_NAME, "user_name": USER, "password": PASSWORD, "administrator": True}
    )
    script = base64.b64encode(CREATE.encode()).decode()
    payload = base64.b64encode(request.encode()).decode()
    vm.ssh(
        f"echo {payload} | base64 -d | runuser -u aegis-setup -- "
        f'python3 -c "$(echo {script} | base64 -d)"'
    )
    login = log_in_at_greeter(vm, logdir, "performance")
    time.sleep(30)
    vm.ssh("sync")
    vm.ssh("systemctl reboot", check=False)
    time.sleep(10)
    started = time.monotonic()
    vm.wait_for_ssh(300)
    wait_for(vm, "pgrep -f sddm-greeter", 180, "the login screen after a reboot")
    to_greeter = time.monotonic() - started
    login2 = log_in_at_greeter(vm, logdir, "performance-2")
    analyze = vm.ssh("systemd-analyze time; systemd-analyze blame | head -n 12", check=False).stdout
    numbers = {
        "first start to AEGIS Setup (s)": round(to_setup, 1),
        "reboot to login screen (s)": round(to_greeter, 1),
        "password to desktop, first login (s)": round(login, 1),
        "password to desktop, later login (s)": round(login2, 1),
    }
    log(logdir, "performance", json.dumps(numbers) + "\n" + analyze)
    for key, value in numbers.items():
        record_property(key, value)
    assert to_greeter < 180 and login2 < 120


def test_idle_desktop_cpu_memory_and_swap(vm, logdir, record_property):
    time.sleep(45)  # the desktop settles; the Welcome tour was closed by the login helper
    hz = int(vm.ssh("getconf CLK_TCK").stdout.strip() or 100)
    names = ("kwin_wayland", "plasmashell")
    before = ticks(vm, names)
    time.sleep(30)
    after = ticks(vm, names)
    cpu = {n: round(100 * (after[n] - before[n]) / hz / 30, 1) for n in names}
    memory = vm.ssh("free -m").stdout
    swap = vm.ssh("swapon --show --bytes --noheadings; zramctl 2>/dev/null || true").stdout
    rss = vm.ssh(f"ps -u {USER} -o rss=,comm= --sort=-rss | head -n 8", check=False).stdout
    used = int(memory.splitlines()[1].split()[2])
    log(
        logdir,
        "performance",
        f"idle CPU over 30 s (100% = one CPU): {cpu}\n{memory}swap:\n{swap or 'none'}\n"
        f"largest processes (RSS KiB):\n{rss}",
    )
    record_property("idle_cpu", json.dumps(cpu))
    record_property("memory_used_mib", used)
    assert "zram" in swap, "no zram swap device"
    assert cpu["kwin_wayland"] < 10 and cpu["plasmashell"] < 10, cpu
    assert used < 2500, f"{used} MiB used on the idle desktop"


WINDOWS = """
for (const w of workspace.windowList())
    if (w.normalWindow) console.info("AEGIS-WINDOWS " + String(w.resourceClass));
"""


@pytest.mark.parametrize(
    ("command", "window", "process"),
    [
        ("dolphin", "org.kde.dolphin", "dolphin"),
        ("aegis-welcome --replay", "org.aegisos.welcome", "aegis-welcome"),
        ("aegis-appcenter", "org.aegisos.appcenter", "aegis-appcenter"),
    ],
)
def test_application_start_times(vm, logdir, record_property, command, window, process):
    """Time from starting the application to KWin showing its window (polled about once
    a second, so the figures are accurate to about a second)."""
    started = time.monotonic()
    as_user(vm, f"systemd-run --user --collect --quiet {command}", check=False)
    seconds = None
    while time.monotonic() - started < 90:
        if any(row and row[0] == window for row in kwin(vm, WINDOWS, "AEGIS-WINDOWS")):
            seconds = time.monotonic() - started
            break
    assert seconds is not None, f"no {window} window within 90 s"
    log(logdir, "performance", f"{command}: window shown after {seconds:.1f} s")
    record_property(f"window_{process}_s", round(seconds, 1))
    time.sleep(3)
    vm.ssh(f"pkill -u {USER} -x {process}", check=False)
    time.sleep(2)


def test_disk_use_and_clean_power_off(vm, logdir):
    use = vm.ssh("df -h --output=target,size,used,avail /var /sysroot 2>/dev/null").stdout
    log(logdir, "performance", f"disk use:\n{use}")
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0

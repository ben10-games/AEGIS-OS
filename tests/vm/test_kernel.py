"""Kernel baseline of the development variant: V-03 (kernel state) and V-19 (settings).

Tests in this module run in order against one virtual machine.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SSH_DEADLINE_S = 120
RUNNING_DEADLINE_S = 180
GOLDEN = Path(__file__).resolve().parents[1] / "golden"


def golden(name: str) -> list[str]:
    lines = (GOLDEN / name).read_text().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


@pytest.fixture(scope="module")
def guest(vm):
    vm.start()
    vm.wait_for_ssh(SSH_DEADLINE_S)
    state = vm.ssh("systemctl is-system-running --wait", timeout=RUNNING_DEADLINE_S, check=False)
    assert state.stdout.strip() == "running", f"system state: {state.stdout.strip()}"
    return vm


def test_v03_running_kernel_is_the_one_in_the_image(guest):
    """V-03: exactly one kernel is installed and it is the one running."""
    installed = guest.ssh("ls /usr/lib/modules").stdout.split()
    assert len(installed) == 1, f"kernels in the image: {installed}"
    assert guest.ssh("uname -r").stdout.strip() == installed[0]


def test_v03_kernel_is_not_tainted(guest):
    """V-03: no out-of-tree module, no forced load, no kernel warning."""
    assert guest.ssh("cat /proc/sys/kernel/tainted").stdout.strip() == "0"


def test_v03_kernel_errors_are_all_expected(guest):
    """V-03: every error-level kernel message is on the reviewed allowlist."""
    allowed = [re.compile(pattern) for pattern in golden("kernel-error-allowlist.txt")]
    messages = guest.ssh("journalctl -k -b -p err --no-pager -o cat", check=False).stdout
    unexpected = [
        line
        for line in messages.splitlines()
        if line.strip() and not any(pattern.fullmatch(line.strip()) for pattern in allowed)
    ]
    assert not unexpected, "unexpected kernel errors:\n" + "\n".join(unexpected)


def test_v19_kernel_arguments(guest):
    """V-19: every argument of the golden list is on the running kernel's command line."""
    command_line = guest.ssh("cat /proc/cmdline").stdout.split()
    missing = [arg for arg in golden("kargs.txt") if arg not in command_line]
    assert not missing, f"missing kernel arguments: {missing}\ncommand line: {command_line}"
    forbidden = {"selinux=0", "enforcing=0", "mitigations=off", "nokaslr", "audit=0"}
    assert not forbidden & set(command_line)


def test_v19_kernel_lockdown_is_active(guest):
    """V-19: the lockdown argument took effect (integrity mode)."""
    assert "[integrity]" in guest.ssh("cat /sys/kernel/security/lockdown").stdout


def test_v19_sysctl_values(guest):
    """V-19: every setting of the golden list has that value in the running kernel."""
    expected = dict(line.split("=", 1) for line in golden("sysctl.txt"))
    output = guest.ssh("sysctl " + " ".join(expected)).stdout
    actual = {}
    for line in output.splitlines():
        key, _, value = line.partition("=")
        actual[key.strip()] = value.strip()
    wrong = {
        key: (actual.get(key), want) for key, want in expected.items() if actual.get(key) != want
    }
    assert not wrong, f"sysctl differences (actual, expected): {wrong}"


def test_v19_reverse_path_filter_is_strict_on_every_interface(guest):
    """The kernel uses the larger of 'all' and the interface value, so check each one."""
    values = guest.ssh("grep -H . /proc/sys/net/ipv4/conf/*/rp_filter").stdout.split()
    loose = [entry for entry in values if not entry.endswith(":1")]
    assert values and not loose, f"interfaces without strict reverse-path filtering: {loose}"


def test_shut_down(guest):
    guest.ssh("systemctl poweroff", check=False)
    assert guest.wait_for_exit(60) == 0

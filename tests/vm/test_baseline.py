"""Operating-system baseline of the development variant (task P1-08).

V-17 accounts and V-20 automatic updates, plus checks that the services the baseline
turns off are really off. Image-level manifests are checked in tests/image/.

Tests in this module run in order against one virtual machine.
"""

from __future__ import annotations

import subprocess

import pytest

SSH_DEADLINE_S = 120
RUNNING_DEADLINE_S = 180

# Units the AEGIS preset disables (image/rootfs/usr/lib/systemd/system-preset/05-aegis.preset).
UNITS_TURNED_OFF = [
    "avahi-daemon.service",
    "avahi-daemon.socket",
    "sssd.service",
    "nfs-client.target",
    "rpm-ostree-countme.timer",
    "bootc-fetch-apply-updates.timer",
    "systemd-sysext.service",
    "systemd-confext.service",
]


@pytest.fixture(scope="module")
def guest(vm):
    vm.start()
    vm.wait_for_ssh(SSH_DEADLINE_S)
    state = vm.ssh("systemctl is-system-running --wait", timeout=RUNNING_DEADLINE_S, check=False)
    assert state.stdout.strip() == "running", f"system state: {state.stdout.strip()}"
    return vm


@pytest.mark.parametrize("unit", UNITS_TURNED_OFF)
def test_unit_turned_off_by_the_baseline_is_not_active(guest, unit):
    """A disabled unit must not come back through a dependency or activation."""
    active = guest.ssh(f"systemctl is-active {unit}", check=False).stdout.strip()
    assert active == "inactive", f"{unit} is {active}"
    enabled = guest.ssh(f"systemctl is-enabled {unit}", check=False).stdout.strip()
    assert enabled in {"disabled", "masked"}, f"{unit} is {enabled}"


def test_v20_automatic_update_timer_is_masked(guest):
    """V-20: unattended updates, which reboot the machine, cannot start."""
    state = guest.ssh("systemctl is-enabled bootc-fetch-apply-updates.timer", check=False)
    assert state.stdout.strip() == "masked"
    timers = guest.ssh("systemctl list-timers --all --no-legend --no-pager").stdout
    assert "bootc-fetch-apply-updates" not in timers


def test_v17_root_account_is_locked(guest):
    """V-17: root has no usable password."""
    assert guest.ssh("passwd -S root").stdout.split()[1] == "L"


def test_v17_no_account_has_a_usable_password(guest):
    """V-17: every password field in /etc/shadow is locked or empty-and-disabled."""
    usable = guest.ssh(
        "awk -F: '$2 !~ /^[!*]/ && $2 != \"\" {print $1}' /etc/shadow", check=False
    ).stdout.split()
    empty = guest.ssh("awk -F: '$2 == \"\" {print $1}' /etc/shadow", check=False).stdout.split()
    assert not usable, f"accounts with a password hash: {usable}"
    assert not empty, f"accounts with an EMPTY password: {empty}"


def test_v17_no_regular_users_are_shipped(guest):
    """V-17: the image defines no human accounts."""
    users = guest.ssh("awk -F: '$3 >= 1000 && $3 < 65000 {print $1}' /etc/passwd").stdout.split()
    assert not users, f"regular users in the image: {users}"


def test_v17_ssh_refuses_password_login(guest):
    """V-17 (development variant): the SSH server does not offer password login at all."""
    result = subprocess.run(
        [
            "ssh",
            "-p",
            str(guest.cfg.ssh_port),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "PubkeyAuthentication=no",
            "-o",
            "PreferredAuthentications=password,keyboard-interactive",
            "-o",
            "ConnectTimeout=10",
            "root@127.0.0.1",
            "true",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode != 0, "login without a key succeeded"
    # ssh reports the methods the server still offers: "Permission denied (publickey,...)."
    assert "Permission denied (" in result.stderr, result.stderr
    offered = result.stderr.split("Permission denied (", 1)[1].split(")", 1)[0].split(",")
    assert "password" not in offered and "keyboard-interactive" not in offered, offered
    assert "publickey" in offered, offered


def test_shut_down(guest):
    guest.ssh("systemctl poweroff", check=False)
    assert guest.wait_for_exit(60) == 0

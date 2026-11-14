"""The release variant (aegis-base) boots and powers off, observed without any login.

aegis-base has no remote access by design (ADR-0002), so these tests use only what a
person at the machine would have: the console and the power button.

Tests in this module run in order against one virtual machine.
"""

from __future__ import annotations

import re
import socket

LOGIN_PROMPT = re.compile(r"^\S+ login: ", re.MULTILINE)
FAILED_UNIT = re.compile(r"^\[FAILED\].*$", re.MULTILINE)
POWER_DOWN = re.compile(r"reboot: Power down")

LOGIN_DEADLINE_S = 180
POWEROFF_DEADLINE_S = 90


def test_base_boots_to_login_prompt(base_vm, record_property):
    """The release image reaches a console login prompt with no failed unit."""
    base_vm.start()
    seconds = base_vm.wait_for_serial(LOGIN_PROMPT, LOGIN_DEADLINE_S)
    record_property("login_prompt_seconds", round(seconds, 1))
    failed = FAILED_UNIT.findall(base_vm.serial_text())
    assert not failed, "units failed during boot:\n" + "\n".join(failed)


def test_base_identifies_itself_as_aegis(base_vm):
    """The console prompt carries the AEGIS default hostname, not Fedora's."""
    prompt = LOGIN_PROMPT.search(base_vm.serial_text())
    assert prompt and prompt.group(0).startswith("aegis login:"), f"prompt was: {prompt}"


def test_base_has_no_remote_login(base_vm):
    """Nothing answers on the SSH port: the release image has no SSH server (ADR-0002).

    The harness forwards a host port to guest port 22 and injects a key exactly as it
    does for the development variant, so a listening server would be found.
    """
    banner = b""
    try:
        with socket.create_connection(("127.0.0.1", base_vm.cfg.ssh_port), timeout=5) as sock:
            sock.settimeout(5)
            banner = sock.recv(64)
    except OSError:
        pass  # refused, reset or timed out: nothing is listening
    assert not banner.startswith(b"SSH-"), f"an SSH server answered: {banner!r}"


def test_base_powers_off_on_power_button(base_vm):
    """Pressing the power button shuts the system down cleanly (V-02 for the release image)."""
    base_vm.press_power_button()
    status = base_vm.wait_for_exit(POWEROFF_DEADLINE_S)
    assert status is not None, f"QEMU still running {POWEROFF_DEADLINE_S}s after the power button"
    assert status == 0, f"QEMU exited with status {status}"
    serial = base_vm.serial_text()
    assert POWER_DOWN.search(serial), "kernel did not report an orderly power-off"
    failed = FAILED_UNIT.findall(serial)
    assert not failed, "units failed during shutdown:\n" + "\n".join(failed)

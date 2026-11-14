"""The release variant (aegis-base) boots and powers off, observed without any login.

aegis-base has no remote access by design (ADR-0002), so these tests use only what a
person at the machine would have: the console and the power button.

Tests in this module run in order against one virtual machine.
"""

from __future__ import annotations

import re

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

"""SELinux verification on the development variant (V-08, task P1-09).

Order matters. The first tests look at the system exactly as it booted; the self-test
at the end deliberately causes one denial and checks that it is enforced and logged.

Tests in this module run in order against one virtual machine.
"""

from __future__ import annotations

import re

import pytest

SSH_DEADLINE_S = 120
RUNNING_DEADLINE_S = 180

# Files created in the physical root at the end of the installation, and the type each
# inherits from its directory on an SELinux system. Installed from a host without
# SELinux they were default_t, which caused BUG-1 (see scripts/fix-install-labels).
INSTALL_TIME_FILES = {
    "/sysroot/.bootc-aleph.json": "root_t",
    "/sysroot/boot/grub2": "boot_t",
    "/sysroot/boot/bootupd-state.json": "boot_t",
}
SELFTEST_FILES = {
    "/usr/libexec/aegis/selftest/cat": "aegis_selftest_exec_t",
    "/usr/share/aegis/selftest/allowed": "aegis_selftest_allowed_t",
    "/usr/share/aegis/selftest/forbidden": "aegis_selftest_forbidden_t",
}
# Domains for programs that the policy does not confine. No service may run in them.
UNCONFINED_SERVICE_DOMAINS = ("unconfined_service_t", "initrc_t")


@pytest.fixture(scope="module")
def guest(vm):
    vm.start()
    vm.wait_for_ssh(SSH_DEADLINE_S)
    state = vm.ssh("systemctl is-system-running --wait", timeout=RUNNING_DEADLINE_S, check=False)
    assert state.stdout.strip() == "running", f"system state: {state.stdout.strip()}"
    return vm


def selinux_type(guest, path: str) -> str:
    context = guest.ssh(f"stat -c %C {path}").stdout.strip()
    return context.split(":")[2]


_AUDIT_TIME = re.compile(r"audit\((\d+)\.\d+:\d+\)")


def denials(guest, not_before: float = 0.0) -> list[str]:
    """SELinux denials of the current boot from both records: audit log and journal.

    The whole audit log is read and filtered here by event time, because
    'ausearch -ts boot' returned nothing on the test VM (BUG-6).
    """
    uptime = float(guest.ssh("cut -d' ' -f1 /proc/uptime").stdout)
    now = float(guest.ssh("date +%s").stdout)
    earliest = max(now - uptime - 5, not_before)
    audit = guest.ssh(
        "ausearch -m AVC,USER_AVC,SELINUX_ERR --raw 2>/dev/null | grep denied", check=False
    ).stdout
    found = []
    for line in audit.splitlines():
        stamp = _AUDIT_TIME.search(line)
        if stamp and float(stamp.group(1)) >= earliest:
            found.append(line)
    journal = guest.ssh(
        f"journalctl -b --no-pager -o cat --since=@{int(earliest)} -g 'avc:  denied'",
        check=False,
    ).stdout
    found += [line for line in journal.splitlines() if "denied" in line]
    return found


def test_v08_selinux_is_enforcing_and_cannot_be_disabled_at_boot(guest):
    """V-08: the kernel enforces the targeted policy; no argument turns it off."""
    assert guest.ssh("getenforce").stdout.strip() == "Enforcing"
    assert guest.ssh("cat /sys/fs/selinux/enforce").stdout.strip() == "1"
    status = guest.ssh("sestatus").stdout
    assert re.search(r"Loaded policy name:\s+targeted", status), status
    assert re.search(r"Mode from config file:\s+enforcing", status), status
    command_line = guest.ssh("cat /proc/cmdline").stdout.split()
    assert not {"selinux=0", "enforcing=0"} & set(command_line)


def test_v08_selftest_policy_module_is_loaded(guest):
    """The module built from policy/selinux/ is in the running system's policy store."""
    modules = guest.ssh("semodule -l").stdout.split()
    assert "aegis_selftest" in modules  # development variant only


def test_v08_no_denials_during_boot(guest, logdir):
    """V-08: nothing was denied between power-on and now (this is BUG-1's test)."""
    found = denials(guest)
    (logdir / "selinux-denials-at-boot.txt").write_text("\n".join(found) + "\n")
    assert not found, f"{len(found)} SELinux denials during boot:\n" + "\n".join(found[:6])


def test_v08_install_time_files_have_the_types_bootupd_may_use(guest):
    """BUG-1 root cause: files written at install time are no longer default_t."""
    actual = {path: selinux_type(guest, path) for path in INSTALL_TIME_FILES}
    assert actual == INSTALL_TIME_FILES


def test_v08_no_unlabelled_files(guest):
    """Every file has a label from the policy."""
    unlabelled = guest.ssh(
        "find / /etc /var -xdev -context '*:unlabeled_t:*' 2>/dev/null | head -n 20;"
        " find /sysroot -maxdepth 3 -context '*:unlabeled_t:*' 2>/dev/null | head -n 20",
        timeout=180,
        check=False,
    ).stdout.split()
    assert not unlabelled, f"files without a label: {unlabelled}"
    leftover = guest.ssh(
        "find /sysroot -maxdepth 3 -context '*:default_t:*' 2>/dev/null | head -n 20",
        check=False,
    ).stdout.split()
    assert not leftover, f"files with the catch-all type default_t: {leftover}"


def test_v08_no_service_runs_unconfined(guest):
    """Every service process runs in a domain of its own."""
    processes = guest.ssh("ps -eZ --no-headers").stdout.splitlines()
    unconfined = [line for line in processes if line.split(":")[2] in UNCONFINED_SERVICE_DOMAINS]
    assert not unconfined, "service processes outside a confined domain:\n" + "\n".join(unconfined)


def test_v08_selftest_files_are_labelled_by_the_module(guest):
    """File contexts shipped in a policy module are applied when the image is deployed."""
    actual = {path: selinux_type(guest, path) for path in SELFTEST_FILES}
    assert actual == SELFTEST_FILES


def test_v08_confined_domain_may_do_what_its_policy_allows(guest):
    """Positive control: the self-test program reads the file its policy allows."""
    result = guest.ssh("systemctl start aegis-selftest-allowed.service", check=False)
    shown = guest.ssh(
        "systemctl show aegis-selftest-allowed.service -p Result -p ExecMainStatus"
    ).stdout
    assert result.returncode == 0 and "Result=success" in shown, shown


def test_v08_confined_domain_is_denied_what_its_policy_does_not_allow(guest, logdir):
    """The same program is refused the other file, and the refusal is enforced and logged."""
    started = float(guest.ssh("date +%s").stdout) - 1
    result = guest.ssh("systemctl start aegis-selftest-forbidden.service", check=False)
    shown = guest.ssh(
        "systemctl show aegis-selftest-forbidden.service -p Result -p ExecMainStatus"
    ).stdout
    assert result.returncode != 0, "reading the forbidden file succeeded"
    assert "ExecMainStatus=1" in shown, shown  # cat: Permission denied

    records = [
        line for line in denials(guest, not_before=started) if "aegis_selftest_forbidden_t" in line
    ]
    (logdir / "selinux-selftest-denial.txt").write_text("\n".join(records) + "\n")
    assert records, "the denial was not recorded in the audit log or the journal"
    record = records[0]
    assert "scontext=system_u:system_r:aegis_selftest_t:s0" in record, record
    assert "tclass=file" in record, record
    assert "permissive=0" in record, record


def test_shut_down(guest):
    guest.ssh("systemctl poweroff", check=False)
    assert guest.wait_for_exit(60) == 0

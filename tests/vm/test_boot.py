"""Milestone M1: the image boots, reaches a healthy state, and shuts down cleanly.

V-01 (boot) and V-02 (shutdown) are the acceptance tests. The remaining checks are
early signals for later tasks; they do not replace the full tests defined in the
blueprint (V-06, V-08, B-08).

Tests in this module run in order against one virtual machine.
"""

from __future__ import annotations

import json
import os

from harness import metrics

SSH_DEADLINE_S = 120
RUNNING_DEADLINE_S = 180
POWEROFF_DEADLINE_S = 60

FILESYSTEM_RECOVERY_MARKERS = (
    "recovering journal",
    "replaying log",
    "log replay required",
    "unclean shutdown",
    "orphan cleanup on readonly fs",
)


def save(logdir, name: str, text: str) -> None:
    (logdir / name).write_text(text)


def collect_diagnostics(vm, logdir, tag: str) -> None:
    """Save guest state for the CI artifacts. Never fails the test by itself."""
    commands = {
        "journal": "journalctl -b --no-pager",
        "failed-units": "systemctl --failed --no-pager",
        "systemd-analyze": "systemd-analyze; systemd-analyze blame --no-pager | head -n 25",
        "bootc-status": "bootc status",
        "memory": "free -m",
        "avc": "journalctl -b --no-pager -g 'avc:  denied' || true",
        "lsblk": "lsblk -o NAME,SIZE,FSTYPE,PARTTYPENAME,MOUNTPOINTS",
        "os-release": "cat /usr/lib/os-release; hostname",
        # The boot chain: what the firmware, the boot loader and the kernel report.
        "boot-chain": (
            'echo "command line: $(cat /proc/cmdline)";'
            ' echo "lockdown: $(cat /sys/kernel/security/lockdown)";'
            ' echo "SecureBoot variable: $(od -An -tu1 -j4 -N1'
            " /sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
            ' 2>/dev/null || echo absent)";'
            " journalctl -k -b --no-pager -o cat | grep -iE 'secure ?boot|lockdown' | head -n 6;"
            " echo; findmnt -no SOURCE,FSTYPE,OPTIONS /; findmnt -no TARGET,SOURCE,FSTYPE /sysroot"
            " /etc /var /boot /efi 2>/dev/null;"
            " echo; ls /sysroot; ls /sysroot/composefs /sysroot/state/deploy 2>&1 | head -n 12;"
            " echo; bootctl status --no-pager 2>&1 | head -n 45;"
            " echo; bootctl list --no-pager 2>&1 | head -n 30"
        ),
        # BUG-8: are the units meant to act at shutdown active, and how is /var ordered?
        "shutdown-units": (
            "systemctl status --no-pager --lines=5 aegis-journal-relinquish.service"
            " systemd-journal-flush.service aegis-shutdown-diagnostics.service 2>&1 | head -n 60;"
            " echo; systemctl show var.mount -p ActiveState -p FragmentPath -p What"
            " -p Options -p After"
            " -p Before -p RequiredBy -p WantedBy -p Requires -p BindsTo;"
            " echo; ls -l /usr/lib/systemd/system/local-fs.target.wants/;"
            " echo; grep -E ' /var | /sysroot ' /proc/self/mountinfo;"
            " echo; systemctl cat --no-pager systemd-journal-flush.service"
            " | grep -E 'Exec|Requires|After|Before'"
        ),
        # Candidates for "/var busy at shutdown": what has files open under /var.
        "var-holders": (
            "findmnt -R /var; echo; lsof -n -w /var 2>/dev/null"
            " | awk 'NR > 1 {print $1, $2, $9}' | sort -u | head -n 60"
        ),
        # On the second boot: what the previous shutdown logged about unmounting.
        "previous-shutdown": (
            "journalctl -b -1 -o short-monotonic --no-pager 2>/dev/null"
            " | grep -iE 'var.mount|unmount|busy|auditd|Stopping|Stopped' | tail -n 60"
        ),
        "esp": (
            "esp=$(bootctl --print-esp-path 2>/dev/null);"
            ' echo "ESP: $esp"; find "$esp" -xdev -type f 2>/dev/null | head -n 40;'
            ' cat "$esp"/loader/loader.conf "$esp"/loader/entries/*.conf 2>/dev/null | head -n 40'
        ),
        "selinux-labels": (
            "for type in unlabeled_t default_t; do"
            ' echo "$type: $(find / /etc /var -xdev -context "*:$type:*" 2>/dev/null | wc -l)'
            " in /, /etc, /var;"
            ' $(find /sysroot -maxdepth 2 -context "*:$type:*" 2>/dev/null | wc -l)'
            ' at the top of /sysroot";'
            " done;"
            " find / /etc /var -xdev \\( -context '*:unlabeled_t:*' -o -context '*:default_t:*' \\)"
            " 2>/dev/null | head -n 25;"
            " find /sysroot -maxdepth 2 -context '*:default_t:*' 2>/dev/null | head -n 10"
        ),
        "selinux-store": (
            "sestatus;"
            " ls -d /etc/selinux/targeted/active /var/lib/selinux/targeted/active 2>&1;"
            " grep -Ev '^(#|$)' /etc/selinux/semanage.conf"
        ),
        "ssh-listeners": (
            "systemctl is-enabled sshd.service sshd.socket 2>&1;"
            " systemctl list-units --all --no-legend --plain --no-pager '*ssh*';"
            " ls /run/systemd/generator /run/systemd/generator.late 2>/dev/null | grep -i ssh"
        ),
        "presets": "ls /usr/lib/systemd/system-preset /etc/systemd/system-preset 2>&1",
        "timers": "systemctl list-timers --all --no-pager",
        "accounts": (
            "passwd -S root; awk -F: '$3 >= 1000 && $3 < 65000 {print $1}' /etc/passwd;"
            " awk -F: '$2 !~ /^[!*]/ && $2 != \"\" {print $1}' /etc/shadow"
        ),
    }
    for name, command in commands.items():
        try:
            result = vm.ssh(command, timeout=60, check=False)
            save(logdir, f"{tag}-{name}.txt", result.stdout + result.stderr)
        except Exception as error:  # diagnostics must not mask the real result
            save(logdir, f"{tag}-{name}.txt", f"could not collect: {error}\n")


def assert_system_running(vm, logdir, tag: str) -> None:
    result = vm.ssh("systemctl is-system-running --wait", timeout=RUNNING_DEADLINE_S, check=False)
    state = result.stdout.strip()
    collect_diagnostics(vm, logdir, tag)
    failed = vm.ssh("systemctl --failed --no-legend --plain --no-pager", check=False).stdout
    assert state == "running", f"system state is '{state}', failed units:\n{failed}"
    assert failed.strip() == "", f"failed units:\n{failed}"


def test_v01_boot_reaches_running_state(vm, logdir, record_property):
    """V-01: SSH within 120 s, system state 'running' within 180 s, no failed units."""
    vm.start()
    seconds = vm.wait_for_ssh(SSH_DEADLINE_S)
    record_property("ssh_ready_seconds", round(seconds, 1))
    assert_system_running(vm, logdir, "boot1")


def test_collect_measurements(vm, logdir, record_property):
    """Record startup time, memory and the runtime inventory of the first boot.

    Observations only. They feed the before/after record and the golden manifests;
    thresholds are V-12 (task P1-17).
    """
    measured = metrics.collect(vm, logdir, "boot1")
    record_property("startup_seconds", measured["startup_seconds"].get("total"))
    record_property("memory_in_use_mib", measured["memory_mib"].get("in_use"))
    record_property("running_services", measured["counts"]["running-services"])
    assert measured["startup_seconds"].get("total"), "systemd-analyze reported no startup time"


def os_release(vm) -> dict[str, str]:
    """The guest's os-release as a dictionary, with quotes removed."""
    fields = {}
    for line in vm.ssh("cat /usr/lib/os-release").stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            fields[key] = value.strip().strip('"')
    return fields


def test_booted_system_is_the_built_image(vm, record_property):
    """The running system is the AEGIS dev image built from this commit."""
    release = os_release(vm)
    assert release["ID"] == "aegis"
    assert release["ID_LIKE"] == "fedora"
    assert release["NAME"] == "AEGIS OS"
    assert release["VARIANT_ID"] == "dev"
    assert release["IMAGE_ID"] == "aegis-dev"
    expected = os.environ.get("AEGIS_EXPECT_REVISION")
    if expected:
        assert release["BUILD_ID"] == expected
    # Problems with AEGIS must not be sent to Fedora or Red Hat.
    assert not [key for key in release if key.startswith("REDHAT_")]
    assert "fedoraproject" not in release["BUG_REPORT_URL"]
    assert vm.ssh("hostname").stdout.strip() == "aegis"

    status = json.loads(vm.ssh("bootc status --format json").stdout)
    booted = status["status"]["booted"]
    assert booted is not None, "bootc reports no booted deployment"
    record_property("booted_image", str((booted.get("image") or {}).get("image")))
    record_property("kernel", vm.ssh("uname -r").stdout.strip())
    record_property("bootc", vm.ssh("bootc --version").stdout.strip())


def test_selinux_is_enforcing(vm):
    """Early signal for V-08: the kernel enforces the SELinux policy."""
    assert vm.ssh("getenforce").stdout.strip() == "Enforcing"


def test_usr_is_read_only(vm):
    """Early signal for V-06: the operating system tree cannot be modified at runtime."""
    result = vm.ssh("touch /usr/aegis-write-probe", check=False)
    assert result.returncode != 0, "/usr is writable"
    assert "Read-only file system" in result.stderr


def test_disk_layout(vm):
    """B-08: GPT with an EFI system partition; root filesystem is btrfs (ADR-0005)."""
    assert vm.ssh("findmnt -no FSTYPE /sysroot").stdout.strip() == "btrfs"
    partition_types = vm.ssh("lsblk -rno PARTTYPENAME /dev/vda").stdout
    assert "EFI\\x20System" in partition_types or "EFI System" in partition_types
    assert vm.ssh("lsblk -dno PTTYPE /dev/vda").stdout.strip() == "gpt"


def test_state_survives_reboot_marker(vm):
    """Write sentinels that the second boot must still see (start of V-09)."""
    vm.ssh("echo aegis-m1 > /etc/aegis-sentinel && echo aegis-m1 > /var/aegis-sentinel && sync")


def test_v02_clean_shutdown(vm):
    """V-02: after 'poweroff' QEMU exits with status 0 within 60 s."""
    first_boot_serial = vm.serial_log
    vm.ssh("systemctl poweroff", check=False)
    status = vm.wait_for_exit(POWEROFF_DEADLINE_S)
    assert status is not None, f"QEMU still running {POWEROFF_DEADLINE_S}s after poweroff"
    assert status == 0, f"QEMU exited with status {status}"
    vm.kill()  # closes the log file handle; the process has already exited
    serial = first_boot_serial.read_text(errors="replace")
    assert "reboot: Power down" in serial, "kernel did not report an orderly power-off"


def test_v02_second_boot_is_clean(vm, logdir):
    """V-02: the next boot is healthy and shows no filesystem recovery."""
    vm.start()
    vm.wait_for_ssh(SSH_DEADLINE_S)
    assert_system_running(vm, logdir, "boot2")

    kernel_log = vm.ssh("journalctl -k -b --no-pager").stdout.lower()
    found = [marker for marker in FILESYSTEM_RECOVERY_MARKERS if marker in kernel_log]
    assert not found, f"filesystem recovery after a clean shutdown: {found}"

    assert vm.ssh("cat /etc/aegis-sentinel").stdout.strip() == "aegis-m1"
    assert vm.ssh("cat /var/aegis-sentinel").stdout.strip() == "aegis-m1"

    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(POWEROFF_DEADLINE_S) == 0

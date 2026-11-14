"""Collect measurements and runtime inventory from a booted guest.

These are observations for the before/after record and the golden manifests. Nothing
here decides pass or fail; thresholds belong to V-12 (task P1-17).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# "1.078s (kernel)", "3min 2.5s (userspace)", "812ms (loader)"
_PHASE = re.compile(r"((?:\d+min )?[\d.]+m?s) \((\w+)\)")
_TOTAL = re.compile(r"= ((?:\d+min )?[\d.]+m?s)")

RUNTIME_LISTS = {
    "running-services": (
        "systemctl list-units --type=service --state=running --no-legend --plain --no-pager"
        " | awk '{print $1}' | LC_ALL=C sort"
    ),
    "enabled-units": (
        "systemctl list-unit-files --state=enabled --no-legend --no-pager"
        " | awk '{print $1}' | LC_ALL=C sort"
    ),
    "active-timers": (
        "systemctl list-units --type=timer --state=active --no-legend --plain --no-pager"
        " | awk '{print $1}' | LC_ALL=C sort"
    ),
    # protocol and local address:port of every TCP/UDP listener
    "listening-sockets": "ss -Htuln | awk '{print $1, $5}' | LC_ALL=C sort -u",
    "listening-vsock": "ss -H --vsock -ln 2>&1 | awk '{print $1, $5}' | LC_ALL=C sort -u",
    "process-domains": (
        "ps -eZ --no-headers | awk '{print $1}' | LC_ALL=C sort | uniq -c | sort -rn"
    ),
    "kernel-errors": "journalctl -k -b -p err --no-pager -o cat",
    "avc-denials": "journalctl -b --no-pager -o cat -g 'avc:  denied' || true",
}


def parse_duration(text: str) -> float:
    """Convert systemd's '1min 2.5s', '3.775s' or '812ms' to seconds."""
    seconds = 0.0
    for value, unit in re.findall(r"([\d.]+)(min|ms|s)", text):
        seconds += float(value) * {"min": 60.0, "s": 1.0, "ms": 0.001}[unit]
    return round(seconds, 3)


def parse_systemd_analyze(text: str) -> dict[str, float]:
    """Parse the first line of 'systemd-analyze' into seconds per boot phase."""
    line = text.splitlines()[0] if text else ""
    phases = {name: parse_duration(value) for value, name in _PHASE.findall(line)}
    total = _TOTAL.search(line)
    if total:
        phases["total"] = parse_duration(total.group(1))
    return phases


def parse_meminfo(text: str) -> dict[str, int]:
    """Return selected /proc/meminfo fields in MiB, plus memory in use."""
    values = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        fields = rest.split()
        if fields and fields[0].isdigit():
            values[key] = int(fields[0]) // 1024
    result = {key: values[key] for key in ("MemTotal", "MemAvailable") if key in values}
    if len(result) == 2:
        result["in_use"] = result["MemTotal"] - result["MemAvailable"]
    return result


def lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def collect(vm, directory: Path, tag: str) -> dict:
    """Gather measurements over SSH; write <tag>-metrics.json and one text file per list."""
    directory.mkdir(parents=True, exist_ok=True)
    lists = {}
    for name, command in RUNTIME_LISTS.items():
        output = vm.ssh(command, timeout=60, check=False).stdout
        lists[name] = lines(output)
        (directory / f"{tag}-{name}.txt").write_text(output)

    metrics = {
        "startup_seconds": parse_systemd_analyze(vm.ssh("systemd-analyze", check=False).stdout),
        "memory_mib": parse_meminfo(vm.ssh("cat /proc/meminfo").stdout),
        "processes": int(vm.ssh("ps -e --no-headers | wc -l").stdout.strip() or 0),
        "kernel_tainted": int(vm.ssh("cat /proc/sys/kernel/tainted").stdout.strip()),
        "kernel_command_line": vm.ssh("cat /proc/cmdline").stdout.strip(),
        "failed_units": lines(
            vm.ssh("systemctl --failed --no-legend --plain --no-pager", check=False).stdout
        ),
        "counts": {name: len(values) for name, values in lists.items()},
    }
    (directory / f"{tag}-metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics

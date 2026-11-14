"""Unit tests for the measurement parsers (no virtual machine needed)."""

from harness.metrics import parse_duration, parse_meminfo, parse_systemd_analyze


def test_parse_duration_units():
    assert parse_duration("3.775s") == 3.775
    assert parse_duration("812ms") == 0.812
    assert parse_duration("1min 2.5s") == 62.5


def test_parse_systemd_analyze_as_printed_in_ci():
    text = (
        "Startup finished in 1.078s (kernel) + 3.775s (initrd) + 6.816s (userspace) = 11.670s \n"
        "graphical.target reached after 6.813s in userspace.\n"
    )
    assert parse_systemd_analyze(text) == {
        "kernel": 1.078,
        "initrd": 3.775,
        "userspace": 6.816,
        "total": 11.67,
    }


def test_parse_systemd_analyze_with_firmware_and_minutes():
    text = (
        "Startup finished in 2.1s (firmware) + 812ms (loader) + 1min 3s (userspace) = 1min 5.912s"
    )
    parsed = parse_systemd_analyze(text)
    assert parsed["firmware"] == 2.1
    assert parsed["loader"] == 0.812
    assert parsed["userspace"] == 63.0
    assert parsed["total"] == 65.912


def test_parse_systemd_analyze_tolerates_empty_output():
    assert parse_systemd_analyze("") == {}


def test_parse_meminfo_reports_mib_and_memory_in_use():
    text = "MemTotal:        3987456 kB\nMemFree:         3400000 kB\nMemAvailable:    3514368 kB\n"
    assert parse_meminfo(text) == {"MemTotal": 3894, "MemAvailable": 3432, "in_use": 462}

"""The golden lists of kernel arguments and sysctl values match what the image ships."""

import tomllib


def golden(root, name):
    lines = (root / "tests" / "golden" / name).read_text().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def test_kernel_arguments_match_golden(root):
    path = root / "image/rootfs/usr/lib/bootc/kargs.d/10-aegis.toml"
    shipped = tomllib.loads(path.read_text())["kargs"]
    assert shipped == golden(root, "kargs.txt")


def test_sysctl_settings_match_golden(root):
    path = root / "image/rootfs/usr/lib/sysctl.d/60-aegis-hardening.conf"
    shipped = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#") or "*" in line:
            continue
        key, _, value = line.partition("=")
        shipped.append(f"{key.strip()}={value.strip()}")
    assert shipped == golden(root, "sysctl.txt")


def test_no_kernel_argument_disables_a_protection(root):
    """Arguments that switch security features off must never be shipped."""
    forbidden = ("selinux=0", "enforcing=0", "mitigations=off", "nokaslr", "audit=0")
    assert not set(golden(root, "kargs.txt")) & set(forbidden)

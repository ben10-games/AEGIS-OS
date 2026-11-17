"""B-06: structure of the sealed images, checked offline.

The facts are collected by scripts/inventory-sealed in the tools container, with each
image mounted read-only and the public Secure Boot certificates of this build.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "out" / "inventory"
GOLDEN = ROOT / "tests" / "golden"
VARIANTS = ["base", "dev"]


def facts(variant: str) -> dict[str, str]:
    path = INVENTORY / variant / "sealed.txt"
    if not path.is_file():
        pytest.fail(f"{path} not found; run 'make inventory' after 'make image'")
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def golden_kernel_arguments() -> list[str]:
    lines = (GOLDEN / "kargs.txt").read_text().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


@pytest.mark.parametrize("variant", VARIANTS)
def test_b06_exactly_one_uki_and_no_loose_kernel(variant):
    """The kernel and initramfs exist only inside the one signed UKI."""
    found = facts(variant)
    assert found["uki_count"] == "1"
    assert found["kernel_files_outside_uki"] == "0"


@pytest.mark.parametrize("variant", VARIANTS)
def test_b06_uki_and_boot_loader_are_signed_by_the_enrolled_key_only(variant):
    """Both verify against this build's db certificate and not against another one."""
    found = facts(variant)
    assert found["uki_signed_by_db"] == "yes"
    assert found["boot_loader_signed_by_db"] == "yes"
    # Control: the check can fail. A certificate that signed nothing must not verify.
    assert found["uki_signed_by_untrusted"] == "no"
    assert found["boot_loader_signed_by_untrusted"] == "no"


@pytest.mark.parametrize("variant", VARIANTS)
def test_b06_image_selects_the_composefs_backend_and_systemd_boot(variant):
    """No bootupd (it would select GRUB) and no ostree root configuration."""
    found = facts(variant)
    assert found["bootupd_present"] == "no"
    assert found["ostree_prepare_root_conf_present"] == "no"
    assert found["composefs_setup_root_conf_present"] == "yes"


@pytest.mark.parametrize("variant", VARIANTS)
def test_b06_uki_carries_the_digest_of_this_root_filesystem(variant):
    """The digest in the signed command line is the digest of the image as shipped."""
    found = facts(variant)
    digest = found["digest_recomputed"]
    assert re.fullmatch(r"[0-9a-f]{128}", digest), f"digest computation failed: {digest}"
    arguments = found["cmdline"].split()
    sealed = [arg for arg in arguments if arg.startswith("composefs")]
    assert sealed, f"no composefs argument in: {found['cmdline']}"
    assert any(digest in arg for arg in sealed), "the UKI was sealed for another filesystem"
    # A '?' would make fs-verity optional (bootc's --allow-missing-verity).
    assert not [arg for arg in sealed if "?" in arg]


@pytest.mark.parametrize("variant", VARIANTS)
def test_b06_signed_command_line_has_the_reviewed_arguments(variant):
    """Every golden kernel argument is in the signed command line, and nothing weakens it."""
    arguments = facts(variant)["cmdline"].split()
    missing = [arg for arg in golden_kernel_arguments() if arg not in arguments]
    assert not missing, f"missing from the signed command line: {missing}"
    forbidden = {"selinux=0", "enforcing=0", "mitigations=off", "nokaslr", "audit=0"}
    assert not forbidden & set(arguments)
    assert not [arg for arg in arguments if arg.startswith(("init=", "rd.break", "systemd.unit="))]


def test_b06_each_variant_is_sealed_separately():
    """Different root filesystems must not share a digest."""
    assert facts("base")["digest_recomputed"] != facts("dev")["digest_recomputed"]

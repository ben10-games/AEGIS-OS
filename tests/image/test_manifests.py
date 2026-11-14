"""Golden manifests: what is inside the images must equal what the repository says.

B-02 packages, B-03 enabled units, B-04 setuid/setgid files, plus masked units, file
capabilities, SELinux permissive domains and the files AEGIS changes under /etc.

The inventory is produced by scripts/inventory-image in out/inventory/. A difference
means either an unintended change (fix the image) or an intended one (update the
golden file in the same commit, so the change is visible in review).
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden"
INVENTORY = ROOT / "out" / "inventory"

BASE_MANIFESTS = {
    "packages.txt": "B-02",
    "enabled-units.txt": "B-03",
    "masked-units.txt": "B-03",
    "setuid-files.txt": "B-04",
    "file-capabilities.txt": "B-04",
    "selinux-permissive-domains.txt": "V-08",
    "etc-changes.txt": "ADR-0014",
}
DEV_DELTAS = [
    "packages.delta.txt",
    "enabled-units.delta.txt",
    "masked-units.delta.txt",
    "setuid-files.delta.txt",
    "file-capabilities.delta.txt",
    "etc-changes.delta.txt",
]


def entries(path: Path) -> list[str]:
    """Non-empty lines that are not comments."""
    return [
        line.rstrip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def compare(relative: str) -> None:
    golden = GOLDEN / relative
    actual = INVENTORY / relative
    assert actual.is_file(), f"{actual} not found; run 'make inventory' first"
    assert golden.is_file(), f"golden manifest {golden} is missing"
    expected, found = entries(golden), entries(actual)
    if expected != found:
        diff = "\n".join(
            difflib.unified_diff(
                expected, found, f"golden/{relative}", f"image/{relative}", lineterm="", n=0
            )
        )
        pytest.fail(
            f"{relative}: the image differs from the golden manifest "
            f"({len(expected)} expected, {len(found)} found)\n{diff}",
            pytrace=False,
        )


@pytest.mark.parametrize("name", sorted(BASE_MANIFESTS))
def test_base_image_matches_golden(name):
    compare(f"base/{name}")


@pytest.mark.parametrize("name", DEV_DELTAS)
def test_dev_variant_differs_from_base_only_as_recorded(name):
    compare(f"dev/{name}")


def test_inventory_is_not_trivially_empty():
    """Guard against an inventory step that silently produced nothing."""
    assert len(entries(INVENTORY / "base" / "packages.txt")) > 100
    assert len(entries(INVENTORY / "base" / "enabled-units.txt")) > 5
    assert len(entries(INVENTORY / "base" / "setuid-files.txt")) > 0

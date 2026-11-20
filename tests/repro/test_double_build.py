"""R-01, R-02 and R-03: two independent clean builds of one commit.

scripts/repro-build makes two builds on one CI runner from separate checkouts, separate
container storage and separately fetched and verified inputs, with the same throw-away
keys (they are build inputs and never leave the runner). scripts/repro-evidence records
each build in out/repro/a and out/repro/b.

R-01 (required): identical inputs: base image, RPM lock and RPM files, builder inputs,
     and the installed package set of every image including the builder.
R-02 (required): identical composefs digests of aegis-base and aegis-dev.
R-03 (reported, not gating): identical image IDs (OCI configuration digests) and layers.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
A = Path(os.environ.get("AEGIS_REPRO_A", ROOT / "out" / "repro" / "a"))
B = Path(os.environ.get("AEGIS_REPRO_B", ROOT / "out" / "repro" / "b"))


def evidence(directory: Path) -> dict[str, str]:
    path = directory / "evidence.txt"
    assert path.is_file(), f"{path} not found; run scripts/repro-build first"
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


@pytest.fixture(scope="module")
def builds():
    a, b = evidence(A), evidence(B)
    assert a["revision"] == b["revision"], "the two builds are of different commits"
    return a, b


def lines_differ(name: str, limit: int = 40) -> str:
    a = set((A / name).read_text().splitlines())
    b = set((B / name).read_text().splitlines())
    only_a, only_b = sorted(a - b), sorted(b - a)
    text = [f"{name}: {len(only_a)} lines only in build A, {len(only_b)} only in build B"]
    text += [f"  A: {line}" for line in only_a[:limit]]
    text += [f"  B: {line}" for line in only_b[:limit]]
    return "\n".join(text)


@pytest.mark.parametrize(
    "key",
    [
        "source_date_epoch",
        "base_image",
        "base_image_id",
        "rpm_lock_sha256",
        "rpm_inputs_sha256",
        "builder_inputs_sha256",
    ],
)
def test_r01_identical_inputs(builds, key):
    a, b = builds
    assert a[key] and a[key] == b[key], f"{key}: {a[key]} != {b[key]}"


@pytest.mark.parametrize("image", ["builder", "base", "dev"])
def test_r01_identical_package_sets(builds, image):
    name = f"rpms-{image}.txt"
    assert (A / name).read_text().strip(), f"{name} is empty"
    assert (A / name).read_text() == (B / name).read_text(), lines_differ(name)


@pytest.mark.parametrize("variant", ["base", "dev"])
def test_r02_identical_composefs_digest(builds, variant):
    a, b = builds
    key = f"composefs_{variant}_v1"
    assert len(a[key]) >= 64, f"{key} missing in build A"
    assert a[key] == b[key], f"aegis-{variant}: {a[key]} != {b[key]}\n" + lines_differ(
        f"{variant}.dump"
    )


@pytest.mark.parametrize("image", ["builder", "base", "dev"])
def test_r03_oci_identity_reported(builds, image, record_property):
    """Reported, never failing: Phase 1 does not require bit-for-bit images."""
    a, b = builds
    key = "builder_image_id" if image == "builder" else f"image_id_{image}"
    layers_a = (A / f"layers-{image}.txt").read_text().splitlines()
    layers_b = (B / f"layers-{image}.txt").read_text().splitlines()
    same_layers = sum(x == y for x, y in zip(layers_a, layers_b, strict=False))
    result = "equal" if a[key] == b[key] else "different"
    line = (
        f"R-03 RESULT aegis-{image}: image ID {result} ({a[key][:19]} / {b[key][:19]}); "
        f"{same_layers} of {len(layers_a)}/{len(layers_b)} layers identical"
    )
    print(line)
    record_property("r03", line)
    (ROOT / "out" / "repro").mkdir(parents=True, exist_ok=True)
    with (ROOT / "out" / "repro" / "r03.txt").open("a") as handle:
        handle.write(line + "\n")

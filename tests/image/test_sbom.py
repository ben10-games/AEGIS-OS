"""B-07 (SBOM part): the SPDX documents of both images are valid and complete.

scripts/sbom writes out/sbom/aegis-<variant>.spdx.json with syft. These tests check
the document structure, that the RPM packages it lists are exactly the golden package
list (the same packages as B-02, not only the same count), and that every package of
the image's locked install steps is present in exactly the locked version.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote

import pytest

ROOT = Path(__file__).resolve().parents[2]
SBOM = ROOT / "out" / "sbom"
GOLDEN = ROOT / "tests" / "golden"
SPDX_ID = re.compile(r"^SPDXRef-[A-Za-z0-9.-]+$")


def load_rpmlock():
    spec = importlib.util.spec_from_file_location("rpmlock", ROOT / "scripts" / "rpmlock.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["rpmlock"] = module
    spec.loader.exec_module(module)
    return module


def golden_packages(variant: str) -> set[str]:
    def entries(path):
        return [
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

    names = set(entries(GOLDEN / "base" / "packages.txt"))
    if variant == "dev":
        for line in entries(GOLDEN / "dev" / "packages.delta.txt"):
            (names.add if line[0] == "+" else names.discard)(line[1:])
    return names


def document(variant: str) -> dict:
    path = SBOM / f"aegis-{variant}.spdx.json"
    assert path.is_file(), f"{path} not found; run scripts/sbom first"
    return json.loads(path.read_text())


# The image's RPM database, under either of the paths rpm uses for it in Fedora.
RPMDB_PATHS = ("/usr/lib/sysimage/rpm/rpmdb.sqlite", "/usr/share/rpm/rpmdb.sqlite")
RPMDB = " or ".join(RPMDB_PATHS)


def from_rpmdb(package: dict) -> bool:
    source = package.get("sourceInfo", "")
    return any(source.endswith(f"RPM DB: {path}") for path in RPMDB_PATHS)


def rpm_packages(doc: dict) -> list[dict]:
    return [
        package
        for package in doc["packages"]
        if any(
            ref.get("referenceLocator", "").startswith("pkg:rpm/")
            for ref in package.get("externalRefs", [])
        )
    ]


def rpms(doc: dict, installed: bool = True) -> dict[str, str]:
    """name.arch -> version-release (epoch-less), from the packages' purls. With
    installed=True only packages read from the image's RPM database: syft also reports
    RPM records found elsewhere (for example rpm-ostree's copy of the base image's
    database stored under /sysroot/ostree in the Fedora base), which describe no
    installed software."""
    found = {}
    for package in rpm_packages(doc):
        if installed and not from_rpmdb(package):
            continue
        for ref in package.get("externalRefs", []):
            locator = ref.get("referenceLocator", "")
            if ref.get("referenceType") != "purl" or not locator.startswith("pkg:rpm/"):
                continue
            path, _, query = locator[len("pkg:rpm/") :].partition("?")
            name, _, version = unquote(path.split("/", 1)[1]).partition("@")
            if name == "gpg-pubkey":
                continue
            arch = parse_qs(query).get("arch", ["?"])[0]
            found[f"{name}.{arch}"] = version
    return found


@pytest.mark.parametrize("variant", ["base", "dev"])
def test_sbom_is_valid_spdx(variant):
    doc = document(variant)
    assert doc["spdxVersion"] == "SPDX-2.3"
    assert doc["dataLicense"] == "CC0-1.0"
    assert doc["SPDXID"] == "SPDXRef-DOCUMENT"
    assert doc["name"]
    assert doc["documentNamespace"].startswith(("https://", "http://"))
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", doc["creationInfo"]["created"])
    assert any(c.startswith("Tool: syft") for c in doc["creationInfo"]["creators"])
    ids = [package["SPDXID"] for package in doc["packages"]]
    assert len(ids) == len(set(ids)), "SPDX identifiers are not unique"
    for package in doc["packages"]:
        assert SPDX_ID.match(package["SPDXID"]), package["SPDXID"]
        assert package["name"]
        assert package["downloadLocation"]
    known = set(ids) | {"SPDXRef-DOCUMENT"} | {f["SPDXID"] for f in doc.get("files", [])}
    for relation in doc.get("relationships", []):
        assert relation["spdxElementId"] in known, relation
        target = relation["relatedSpdxElement"]
        assert target in known or target in ("NOASSERTION", "NONE"), relation


@pytest.mark.parametrize("variant", ["base", "dev"])
def test_sbom_lists_exactly_the_golden_packages(variant):
    """B-07: the SPDX file lists the same packages as B-02 (count and names)."""
    doc = document(variant)
    listed = set(rpms(doc))
    expected = golden_packages(variant)
    missing, extra = sorted(expected - listed), sorted(listed - expected)
    elsewhere = sorted(
        f"{p['name']} {p.get('versionInfo', '')} ({p.get('sourceInfo', 'no sourceInfo')})"
        for p in rpm_packages(doc)
        if not from_rpmdb(p)
    )
    assert not missing and not extra, (
        f"missing from SBOM: {missing}; not golden: {extra}; "
        f"RPM records not from {RPMDB}: {elsewhere[:20]}"
    )
    assert len(listed) == len(expected)


@pytest.mark.parametrize("variant", ["base", "dev"])
def test_rpm_records_outside_the_package_database_are_listed(variant):
    """Reported, not a failure: RPM records syft finds outside the RPM database."""
    doc = document(variant)
    others = [p for p in rpm_packages(doc) if not from_rpmdb(p)]
    sources = sorted({p.get("sourceInfo", "?") for p in others})
    print(f"aegis-{variant}: {len(others)} RPM records outside {RPMDB}: {sources[:5]}")
    assert len(rpms(doc)) > 300, "the image's own RPM database was not catalogued"


@pytest.mark.parametrize(("variant", "steps"), [("base", ["base"]), ("dev", ["base", "dev"])])
def test_locked_packages_are_installed_in_the_locked_version(variant, steps):
    """P1-15: what the image's install steps added is exactly what the lock names."""
    lock = load_rpmlock().read_lock(ROOT / "image" / "packages" / "rpms.lock.yaml")
    listed = rpms(document(variant))
    wrong = []
    for package in lock.packages:
        if package.set not in steps:
            continue
        key = f"{package.name}.{package.arch}"
        expected = f"{package.version}-{package.release}"
        found = listed.get(key, "absent").split(":")[-1]
        if found != expected:
            wrong.append(f"{key}: image {found}, lock {expected}")
    assert not wrong, "\n".join(wrong)

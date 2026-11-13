"""S-04: every architecture decision record has a status and appears in the index."""

import re

ALLOWED_STATUS = {"Accepted", "Provisional", "Open", "Superseded"}
REQUIRED_HEADINGS = ["## Context", "## Decision", "## Consequences", "## Verification"]
NAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")


def adr_files(root):
    return sorted(p for p in (root / "docs" / "adr").glob("*.md") if NAME.match(p.name))


def status_of(path):
    match = re.search(r"^Status: (.+)$", path.read_text(), flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def test_adrs_exist_and_numbers_are_unique(root):
    numbers = [NAME.match(p.name).group(1) for p in adr_files(root)]
    assert numbers, "no ADRs found"
    assert len(numbers) == len(set(numbers))


def test_each_adr_has_status_and_sections(root):
    for path in adr_files(root):
        if path.name.startswith("0000-"):
            continue
        assert status_of(path) in ALLOWED_STATUS, f"{path.name}: missing or invalid Status"
        text = path.read_text()
        for heading in REQUIRED_HEADINGS:
            assert heading in text, f"{path.name}: missing '{heading}'"


def test_index_lists_every_adr_with_matching_status(root):
    index = (root / "docs" / "adr" / "README.md").read_text()
    for path in adr_files(root):
        if path.name.startswith("0000-"):
            continue
        row = re.search(
            rf"^\|.*\({re.escape(path.name)}\).*\| (\w+) \|$", index, flags=re.MULTILINE
        )
        assert row, f"{path.name} is not in docs/adr/README.md"
        assert row.group(1) == status_of(path), f"{path.name}: index status differs from file"

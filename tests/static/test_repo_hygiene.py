"""Repository hygiene: no key material, secrets directory ignored, scripts are strict."""

import re
import stat
import subprocess

# Built by concatenation so this file does not itself match the pattern.
PRIVATE_KEY_MARKER = re.compile("-----BEGIN [A-Z0-9 ]*" + "PRIVATE KEY" + "-----")
SECRET_SUFFIXES = {".key", ".p12", ".pfx"}


def test_no_private_key_material_in_repository(files):
    hits = []
    for path in files:
        if path.suffix in SECRET_SUFFIXES:
            hits.append(f"{path}: secret-like file extension")
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        if PRIVATE_KEY_MARKER.search(text):
            hits.append(f"{path}: contains a private key block")
    assert not hits, "\n".join(hits)


def test_secrets_directory_is_ignored(root):
    for path in (".secrets/example.key", ".secrets/cosign.pub", "out/disk.qcow2"):
        result = subprocess.run(["git", "check-ignore", "-q", path], cwd=root, check=False)
        assert result.returncode == 0, f"{path} must be ignored by git"


def test_scripts_are_executable_and_strict(root):
    scripts = [
        p
        for directory in (root / "scripts", root / "image" / "build")
        for p in directory.iterdir()
        if p.is_file()
    ]
    assert scripts, "no scripts found"
    for path in scripts:
        text = path.read_text()
        assert path.stat().st_mode & stat.S_IXUSR, f"{path.name}: not executable"
        assert text.startswith("#!/usr/bin/env bash\n"), f"{path.name}: unexpected shebang"
        assert "set -euo pipefail" in text, f"{path.name}: missing 'set -euo pipefail'"


def test_lint_requirements_are_hash_pinned(root):
    text = (root / "build" / "ci" / "requirements-lint.txt").read_text().replace("\\\n", " ")
    requirements = [line for line in text.splitlines() if line and not line.startswith("#")]
    assert requirements
    for line in requirements:
        assert re.match(r"^[a-z0-9-]+==\S+ ", line), f"not pinned to a version: {line[:40]}"
        assert "--hash=sha256:" in line, f"no hash: {line[:40]}"

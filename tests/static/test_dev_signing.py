"""ADR-0015: the persistent development signing identity is created only inside the
reviewer-gated bootstrap environment, stored only as environment secrets, and never
printed, uploaded or committed."""

import re
import secrets
import subprocess
import sys

WORKFLOW = ".github/workflows/dev-signing-bootstrap.yml"
SCRIPT = "scripts/bootstrap-dev-signing"


def test_bootstrap_is_manual_branch_limited_and_reviewer_gated(root):
    text = (root / WORKFLOW).read_text()
    triggers = text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  (\w+):", triggers, flags=re.MULTILINE) == ["workflow_dispatch"]
    assert "environment: aegis-dev-bootstrap" in text
    assert "github.ref == 'refs/heads/claude/aegis-os-v3'" in text
    assert "inputs.confirm == 'create the development signing identity'" in text
    assert "upload-artifact" not in text
    assert "packages: write" not in text
    assert text.count("AEGIS_DEV_BOOTSTRAP_TOKEN") == 1


def test_bootstrap_keeps_private_keys_off_disk_logs_and_arguments(root):
    text = (root / SCRIPT).read_text()
    assert "mount -t tmpfs" in text and "trap cleanup EXIT" in text
    assert "refusing to replace the identity" in text
    # Secrets reach gh only on standard input.
    for line in text.splitlines():
        if "gh secret set" in line:
            assert "--body" not in line and "-b " not in line
    # Only public halves are printed between the markers.
    public = text.split('echo "BEGIN AEGIS DEV PUBLIC KEYS"', 1)[1]
    assert ".key" not in public.replace(".crt", "")
    assert "aegis-os.private" not in public and "passphrase" not in public
    assert 'AEGIS_SB_KEY_LABEL="persistent development key, not for production"' in text


def test_key_material_scanner_finds_a_key_on_a_sparse_disk(root, tmp_path):
    body = [secrets.token_urlsafe(48)[:64] for _ in range(6)]
    key = tmp_path / "db.key"
    marker = "PRIVATE " + "KEY"
    key.write_text(f"-----BEGIN {marker}-----\n" + "\n".join(body) + f"\n-----END {marker}-----\n")
    disk = tmp_path / "disk.raw"
    with disk.open("wb") as handle:
        handle.truncate(512 << 20)  # sparse
        handle.seek(300 << 20)
        handle.write(f"docs: -----BEGIN {marker}----- example".encode() * 4)
    scan = [sys.executable, "-I", str(root / "scripts/find_key_material.py"), str(disk), str(key)]
    clean = subprocess.run(scan, capture_output=True, text=True)
    assert clean.returncode == 0, clean.stderr
    with disk.open("r+b") as handle:
        handle.seek((400 << 20) - 10)  # across a read-block boundary is fine too
        handle.write(key.read_bytes())
    found = subprocess.run(scan, capture_output=True, text=True)
    assert found.returncode == 1 and "key material of" in found.stderr
    assert not any(line in found.stderr + found.stdout for line in body)

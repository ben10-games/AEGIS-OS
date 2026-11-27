"""ADR-0015: the persistent development signing identity is created only inside the
reviewer-gated bootstrap environment, stored only as environment secrets, and never
printed, uploaded or committed."""

import re
import secrets
import subprocess
import sys

WORKFLOW = ".github/workflows/dev-signing-bootstrap.yml"
SCRIPT = "scripts/bootstrap-dev-signing"


def test_bootstrap_is_branch_limited_preflighted_and_reviewer_gated(root):
    text = (root / WORKFLOW).read_text()
    triggers = text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  (\w+):", triggers, flags=re.MULTILINE) == ["push", "workflow_dispatch"]
    # Only a change of the request file starts it, and only with the marker at the very
    # beginning of the commit message (run 46015720213 was started by a message that
    # merely mentioned the marker).
    assert re.search(r"paths:\n\s+- keys/dev/bootstrap-request\n", triggers)
    assert "startsWith(github.event.head_commit.message, '[bootstrap-dev-signing]')" in text
    assert "contains(github.event.head_commit.message" not in text
    jobs = text.split("\njobs:\n", 1)[1]
    preflight, bootstrap = jobs.split("\n  bootstrap:\n", 1)
    # The preflight holds no secret and names no environment; it checks both.
    assert "environment:" not in preflight and "AEGIS_DEV" not in preflight
    assert "required_reviewers" in preflight and "custom_branch_policies" in preflight
    assert "actions: read" in preflight
    # The bootstrap job exists only after the preflight passed.
    assert "needs: preflight" in bootstrap
    assert "environment: aegis-dev-bootstrap" in bootstrap
    assert "upload-artifact" not in text
    assert "packages: write" not in text
    assert text.count("AEGIS_DEV_BOOTSTRAP_TOKEN") == 1


def test_bootstrap_keeps_private_keys_off_disk_logs_and_arguments(root):
    text = (root / SCRIPT).read_text()
    assert "mount -t tmpfs" in text and "trap cleanup EXIT" in text
    assert "refusing to replace the identity" in text
    # The environments' protection is checked before any key is generated.
    assert text.index("custom_branch_policies") < text.index("scripts/dev-keys")
    assert text.index("required_reviewers") < text.index("scripts/dev-keys")
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

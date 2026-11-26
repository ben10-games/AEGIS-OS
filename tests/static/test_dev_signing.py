"""ADR-0015: the persistent development signing identity is created only inside the
reviewer-gated bootstrap environment, stored only as environment secrets, and never
printed, uploaded or committed."""

import re
import subprocess

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


def test_no_private_key_material_is_committed(root):
    tracked = (
        subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
        .stdout.decode()
        .split("\0")
    )
    for name in filter(None, tracked):
        path = root / name
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        assert "PRIVATE KEY-----" not in text or path.suffix in {".py", ".md"}, name
        assert "ENCRYPTED SIGSTORE PRIVATE KEY" not in text or path.suffix == ".py", name

"""Signed updates and rollback under Secure Boot: V-13, V-14, V-15 and V-09 (task P1-14).

A test registry (harness/registry.py) runs inside the offline test container. It serves
the update image of this build under three tags:

- v2: signed with this build's AEGIS signing key (the key whose public half is sealed
  into the image),
- v3: the same image content under a different manifest, unsigned,
- v4: the same image in a separate repository (aegis-dev-untrusted), signed only with
  a key nobody trusts.

The guest is told only one thing at test time: that ghcr.io/ben10-games/aegis-os has a
mirror at the test registry (registries.conf drop-in). The image's own signature policy
(/etc/containers/policy.json, default reject) and public key are used unchanged, and the
signatures name the real repository, so the guest checks them exactly as it would for
images from GHCR.

Tests run in order against one virtual machine booted with Secure Boot: refused updates
first, then v1 -> v2, then the rollback v2 -> v1.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

import pytest
from harness.registry import Registry

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "ghcr.io/ben10-games/aegis-os/aegis-dev"
UNTRUSTED_REPOSITORY = "ghcr.io/ben10-games/aegis-os/aegis-dev-untrusted"
SIGNING = ROOT / ".secrets" / "signing"
UPDATE_ARCHIVE = ROOT / "out" / "images" / "aegis-dev-v2.oci.tar"
SSH_DEADLINE_S = 180
SWITCH_TIMEOUT_S = 1200
EFI_GLOBAL = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
SENTINEL = "aegis-v09-sentinel"


def sealed_digest(variant: str) -> str:
    return (ROOT / "out" / "digests" / f"{variant}.v1").read_text().strip()


def skopeo_push(
    registry: Registry, workdir: Path, tag: str, extra: list[str], repository: str = "aegis-dev"
) -> str:
    """Push the update image to the test registry; return the manifest digest."""
    registries_d = workdir / "registries.d"
    registries_d.mkdir(exist_ok=True)
    (registries_d / "test.yaml").write_text(
        f"docker:\n  127.0.0.1:{registry.port}/aegis-os:\n    use-sigstore-attachments: true\n"
    )
    policy = workdir / "push-policy.json"
    policy.write_text(json.dumps({"default": [{"type": "insecureAcceptAnything"}]}))
    destination = f"docker://127.0.0.1:{registry.port}/aegis-os/{repository}:{tag}"
    digest_file = workdir / f"{tag}.digest"
    subprocess.run(
        ["skopeo", "--policy", str(policy), "--registries.d", str(registries_d), "copy",
         "--dest-tls-verify=false", "--digestfile", str(digest_file), *extra,
         f"oci-archive:{UPDATE_ARCHIVE}", destination],
        check=True, capture_output=True, text=True, timeout=1800,
    )  # fmt: skip
    return digest_file.read_text().strip()


def signed_by(key: str, reference: str) -> list[str]:
    return [
        "--sign-by-sigstore-private-key", str(SIGNING / f"{key}.private"),
        "--sign-passphrase-file", str(SIGNING / "passphrase"),
        "--sign-identity", reference,
    ]  # fmt: skip


@pytest.fixture(scope="module")
def registry(workdir, logdir):
    """The test registry with v2 (signed), v3 (unsigned) and v4 (untrusted signer)."""
    if not UPDATE_ARCHIVE.is_file():
        pytest.fail(f"{UPDATE_ARCHIVE} not found; it is written by 'make image'")
    root = workdir / "registry"
    with Registry(root / "data") as running:
        # skopeo reuses blobs the registry already has, so the same image content
        # cannot be given a third distinct manifest by recompression. v4 is therefore
        # the v2 image in a repository of its own, where its only signature is by the
        # untrusted key (sigstore attachments are stored per repository). The
        # repository is under the AEGIS prefix, so the image's policy applies to it.
        digests = {
            "v2": skopeo_push(running, root, "v2", signed_by("aegis-os", f"{REPOSITORY}:v2")),
            "v3": skopeo_push(running, root, "v3", ["--format", "v2s2"]),
            "v4": skopeo_push(
                running, root, "v4",
                signed_by("untrusted", f"{UNTRUSTED_REPOSITORY}:v4"),
                repository="aegis-dev-untrusted",
            ),
        }  # fmt: skip
        (logdir / "update-registry.txt").write_text(json.dumps(digests, indent=2) + "\n")
        assert digests["v2"] != digests["v3"], f"v3 must be a different manifest: {digests}"
        yield running, digests


def boot_id(vm) -> str:
    return vm.ssh("cat /proc/sys/kernel/random/boot_id").stdout.strip()


def reboot(vm) -> None:
    """Reboot the guest and wait until it is back with a new boot id."""
    before = boot_id(vm)
    vm.ssh("systemctl reboot", check=False)
    deadline = time.monotonic() + SSH_DEADLINE_S * vm.timeout_scale
    while time.monotonic() < deadline:
        time.sleep(5)
        result = vm.ssh("cat /proc/sys/kernel/random/boot_id", check=False, timeout=20)
        if result.returncode == 0 and result.stdout.strip() not in ("", before):
            vm.ssh("systemctl is-system-running --wait", timeout=180, check=False)
            return
    raise AssertionError("the guest did not come back after a reboot")


def running_digest(vm) -> str:
    command_line = vm.ssh("cat /proc/cmdline").stdout
    match = re.search(r"composefs\.digest=v1-sha512-12:([0-9a-f]{128})", command_line)
    assert match, command_line
    return match.group(1)


def bootc_status(vm) -> dict:
    return json.loads(vm.ssh("bootc status --format json").stdout)


def assert_security_properties(vm) -> None:
    """What every booted deployment must show, before and after an update."""
    secure_boot = vm.ssh(
        f"od -An -tu1 -j4 -N1 /sys/firmware/efi/efivars/SecureBoot-{EFI_GLOBAL}"
    ).stdout.split()
    assert secure_boot == ["1"], "Secure Boot is not enforced"
    assert vm.ssh("getenforce").stdout.strip() == "Enforcing"
    assert "[integrity]" in vm.ssh("cat /sys/kernel/security/lockdown").stdout
    assert vm.ssh("systemctl is-active aegis-verify-cmdline.service").stdout.strip() == "active"
    assert vm.ssh("systemctl --failed --no-legend --plain").stdout.strip() == ""


@pytest.fixture(scope="module")
def guest(vm, registry, logdir):
    running, _ = registry
    vm.start()
    vm.wait_for_ssh(SSH_DEADLINE_S)
    vm.ssh("systemctl is-system-running --wait", timeout=180, check=False)
    # Test-time configuration: the AEGIS repository is mirrored by the test registry.
    mirror = f"10.0.2.2:{running.port}/aegis-os"
    vm.ssh(
        "cat > /etc/containers/registries.conf.d/50-aegis-test-mirror.conf <<'EOF'\n"
        '[[registry]]\nprefix = "ghcr.io/ben10-games/aegis-os"\n'
        'location = "ghcr.io/ben10-games/aegis-os"\n'
        f'[[registry.mirror]]\nlocation = "{mirror}"\ninsecure = true\nEOF\n'
        "cat > /etc/containers/registries.d/50-aegis-test-mirror.yaml <<'EOF'\n"
        f"docker:\n  {mirror}:\n    use-sigstore-attachments: true\nEOF"
    )
    # V-09 sentinels: machine state that every deployment must keep.
    vm.ssh(f"echo {SENTINEL} > /etc/{SENTINEL}; echo {SENTINEL} > /var/{SENTINEL}")
    yield vm
    (logdir / "update-final-status.txt").write_text(
        vm.ssh("bootc status", check=False).stdout
        + vm.ssh("journalctl -b -u bootc-composefs-finalize-staged --no-pager", check=False).stdout
    )
    vm.ssh("systemctl poweroff", check=False)
    vm.wait_for_exit(120)


def assert_refused(guest, reference: str, logdir: Path) -> str:
    tag = reference.rsplit(":", 1)[1]
    result = guest.ssh(f"bootc switch {reference}", check=False, timeout=SWITCH_TIMEOUT_S)
    (logdir / f"v15-{tag}.txt").write_text(
        f"exit status: {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.returncode != 0, f"bootc accepted {reference}:\n{result.stdout}"
    message = result.stdout + result.stderr
    assert re.search(r"signature|policy|[Rr]ejected", message), message[-1500:]
    assert bootc_status(guest)["status"].get("staged") is None, "something was staged"
    return message


def test_v15_unsigned_update_is_refused(guest, logdir):
    """V-15: an image without a signature is refused; nothing is staged."""
    assert_security_properties(guest)
    assert_refused(guest, f"{REPOSITORY}:v3", logdir)


def test_v15_update_signed_by_an_unknown_key_is_refused(guest, logdir):
    """V-15: a valid signature by a key the image does not trust is refused."""
    assert_refused(guest, f"{UNTRUSTED_REPOSITORY}:v4", logdir)
    assert running_digest(guest) == sealed_digest("dev")


def test_v13_signed_update_is_staged_and_booted(guest, logdir):
    """V-13: v2, signed by the AEGIS key, is staged; after a reboot v2 is running."""
    result = guest.ssh(f"bootc switch {REPOSITORY}:v2", check=False, timeout=SWITCH_TIMEOUT_S)
    (logdir / "v13-switch.txt").write_text(
        f"exit status: {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert bootc_status(guest)["status"].get("staged") is not None, "nothing was staged"
    reboot(guest)
    (logdir / "v13-status.txt").write_text(guest.ssh("bootc status").stdout)
    assert running_digest(guest) == sealed_digest("dev-v2"), "not running the v2 root filesystem"
    assert guest.ssh("cat /usr/share/aegis/update-marker").stdout.strip()
    assert_security_properties(guest)


def test_v09_state_survives_the_update(guest):
    """V-09: /etc and /var keep the machine's state across the update."""
    for path in (f"/etc/{SENTINEL}", f"/var/{SENTINEL}"):
        assert guest.ssh(f"cat {path}").stdout.strip() == SENTINEL


def test_v14_rollback_returns_to_v1(guest, logdir):
    """V-14: 'bootc rollback' and a reboot bring back the v1 root filesystem."""
    result = guest.ssh("bootc rollback", check=False, timeout=300)
    (logdir / "v14-rollback.txt").write_text(
        f"exit status: {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.returncode == 0, result.stderr[-2000:]
    reboot(guest)
    (logdir / "v14-status.txt").write_text(guest.ssh("bootc status").stdout)
    assert running_digest(guest) == sealed_digest("dev"), "not running the v1 root filesystem"
    assert guest.ssh("test -e /usr/share/aegis/update-marker", check=False).returncode != 0
    assert_security_properties(guest)


def test_v09_state_survives_the_rollback(guest):
    """V-09: /etc and /var keep the machine's state across the rollback."""
    for path in (f"/etc/{SENTINEL}", f"/var/{SENTINEL}"):
        assert guest.ssh(f"cat {path}").stdout.strip() == SENTINEL

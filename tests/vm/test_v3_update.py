"""AEGIS OS v3 (M9): a signed system update and a rollback on the persistent VDI, with the
user's applications, account, files and settings kept throughout.

Version A is the exported VDI (through a copy-on-write overlay). Version B is the v3
image plus an update marker (image/Containerfile.update on aegis-v3-rootfs), sealed and
signed like any image and never released. A test registry (harness/registry.py) inside
the test container serves B under the AEGIS repository name:

- aegis-v3:b            signed with the build's AEGIS signing key,
- aegis-v3:unsigned     the same content, no signature,
- aegis-v3-untrusted:b  signed only with a key nobody trusts.

As in tests/vm/test_update.py, the guest is told only that ghcr.io/ben10-games/aegis-os
has a mirror at the test registry; its own signature policy (default reject, AEGIS key
only) is used unchanged.

Order, in one VM on VirtualBox-like hardware (no Secure Boot keys, as in VirtualBox):
version A with an account, Google Chrome from Flathub, a file, colour scheme, glass
profile and wallpaper; the unsigned and untrusted updates are refused; the signed update
to B is staged and booted; everything is still there; rollback to A; everything is
still there. Needs the internet for Flathub (same hosts as the other Flatpak suites).

Within one CI run A and B are signed with the same per-build key. With the persistent
development identity (ADR-0015), A comes from an earlier run (cross-build); see
PROJECT_STATE.md for which form a given result is. This is QEMU, not VirtualBox.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import pytest
from harness.registry import Registry
from test_update import bootc_status, reboot, running_digest, signed_by, skopeo_push
from test_v3_apps import CHROME, CREATE, INSTALL_TIMEOUT_S, chrome_starts
from test_v3_vdi import (
    FULL_NAME,
    PASSWORD,
    TOKEN,
    USER,
    as_user,
    boot,
    log,
    log_in_at_greeter,
    shot,
    vdi,  # noqa: F401  (fixture)
    vdi_machine,
    wait_for,
)

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "ghcr.io/ben10-games/aegis-os/aegis-v3"
UNTRUSTED_REPOSITORY = "ghcr.io/ben10-games/aegis-os/aegis-v3-untrusted"
ARCHIVE = ROOT / "out" / "images" / "aegis-v3-update.oci.tar"
SWITCH_TIMEOUT_S = 1800
WALLPAPER = "/usr/share/wallpapers/AEGIS/contents/images/1920x1080.png"


def sealed_digest(variant: str) -> str:
    return (ROOT / "out" / "digests" / f"{variant}.v1").read_text().strip()


@pytest.fixture(scope="module")
def registry(workdir, logdir):
    if not ARCHIVE.is_file():
        pytest.fail(f"{ARCHIVE} not found; build with AEGIS_V3_UPDATE=1")
    root = workdir / "v3-registry"
    root.mkdir(exist_ok=True)
    with Registry(root / "data") as running:
        digests = {
            "b": skopeo_push(
                running, root, "b", signed_by("aegis-os", f"{REPOSITORY}:b"),
                repository="aegis-v3", archive=ARCHIVE,
            ),
            "unsigned": skopeo_push(
                running, root, "unsigned", ["--format", "v2s2"],
                repository="aegis-v3", archive=ARCHIVE,
            ),
            "untrusted": skopeo_push(
                running, root, "b", signed_by("untrusted", f"{UNTRUSTED_REPOSITORY}:b"),
                repository="aegis-v3-untrusted", archive=ARCHIVE,
            ),
        }  # fmt: skip
        log(logdir, "update", f"test registry: {json.dumps(digests)}")
        yield running


@pytest.fixture(scope="module")
def vm(vdi, workdir, logdir, accel, registry):  # noqa: F811
    with vdi_machine(vdi, workdir, logdir, accel, "v3-update", cpus=4) as machine:
        yield machine


def user_state(vm) -> dict[str, str]:
    home = f"/var/home/{USER}"
    return {
        "file": vm.ssh(f"cat {home}/Documents/aegis-update.txt", check=False).stdout.strip(),
        "colour scheme": as_user(
            vm, "kreadconfig6 --file kdeglobals --group General --key ColorScheme", False
        ).stdout.strip(),
        "glass profile": as_user(
            vm, "kreadconfig6 --file aegis-glassrc --group General --key Profile", False
        ).stdout.strip(),
        "wallpaper": vm.ssh(
            f"grep -h '^Image=' {home}/.config/plasma-org.kde.plasma.desktop-appletsrc || true"
        ).stdout.strip(),
        "account": vm.ssh(f"getent passwd {USER}", check=False).stdout.strip(),
        "groups": vm.ssh(f"id -nG {USER}", check=False).stdout.strip(),
        "apps": as_user(
            vm, "flatpak list --user --app --columns=application", False
        ).stdout.strip(),
    }


def assert_user_state(vm, logdir, label: str) -> None:
    state = user_state(vm)
    log(logdir, "update", f"{label}: " + json.dumps(state))
    assert state["file"] == TOKEN
    assert state["colour scheme"] == "AEGISLight"
    assert state["glass profile"] == "performance"
    assert WALLPAPER in state["wallpaper"]
    assert f":{FULL_NAME}:" in state["account"]
    assert "wheel" in state["groups"].split()
    assert CHROME in state["apps"].split()


def assert_system(vm, logdir, label: str, variant: str) -> None:
    digest = running_digest(vm)
    log(logdir, "update", f"{label}: running digest {digest[:16]}…, expected {variant}")
    assert digest == sealed_digest(variant), f"not running {variant}"
    assert vm.ssh("getenforce").stdout.strip() == "Enforcing"
    assert vm.ssh("systemctl is-active aegis-verify-cmdline.service").stdout.strip() == "active"
    failed = vm.ssh("systemctl --failed --no-legend --plain").stdout.strip()
    denials = vm.ssh("journalctl -b --no-pager -o cat | grep 'avc:  denied' || true").stdout
    log(logdir, "update-denials", f"{label}: {denials.strip() or 'none'}")
    assert not failed, failed
    assert not denials.strip(), denials[:3000]


def test_version_a_with_applications_and_settings(vm, logdir):
    boot(vm, logdir, "update A")
    wait_for(vm, "pgrep -u aegis-setup -x aegis-setup", 240, "AEGIS Setup")
    request = json.dumps(
        {"full_name": FULL_NAME, "user_name": USER, "password": PASSWORD, "administrator": True}
    )
    script = base64.b64encode(CREATE.encode()).decode()
    payload = base64.b64encode(request.encode()).decode()
    reply = vm.ssh(
        f"echo {payload} | base64 -d | runuser -u aegis-setup -- "
        f'python3 -c "$(echo {script} | base64 -d)"'
    ).stdout
    assert '"ok": true' in reply, reply
    log_in_at_greeter(vm, logdir, "update-a")
    home = f"/var/home/{USER}"
    as_user(vm, f"mkdir -p {home}/Documents && echo {TOKEN} > {home}/Documents/aegis-update.txt")
    as_user(vm, "systemd-run --user --wait --collect --quiet plasma-apply-colorscheme AEGISLight")
    as_user(vm, "/usr/libexec/aegis/glass-profile apply performance")
    as_user(vm, f"plasma-apply-wallpaperimage {WALLPAPER}", check=False)
    wait_for(
        vm,
        f"runuser -u {USER} -- flatpak remotes --user --columns=name | grep -qx flathub",
        120,
        "the per-user Flathub remote",
    )
    result = as_user(
        vm,
        f"flatpak install --user --noninteractive -y flathub {CHROME} 2>&1",
        check=False,
        timeout=INSTALL_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stdout[-3000:]
    chrome_starts(vm, logdir, "update-a")
    time.sleep(5)
    vm.ssh("sync")
    assert_user_state(vm, logdir, "A before the update")
    assert_system(vm, logdir, "A", "v3")


def test_guest_uses_the_test_registry_as_mirror(vm, registry):
    mirror = f"10.0.2.2:{registry.port}/aegis-os"
    vm.ssh(
        "cat > /etc/containers/registries.conf.d/50-aegis-test-mirror.conf <<'EOF'\n"
        '[[registry]]\nprefix = "ghcr.io/ben10-games/aegis-os"\n'
        'location = "ghcr.io/ben10-games/aegis-os"\n'
        f'[[registry.mirror]]\nlocation = "{mirror}"\ninsecure = true\nEOF\n'
        "cat > /etc/containers/registries.d/50-aegis-test-mirror.yaml <<'EOF'\n"
        f"docker:\n  {mirror}:\n    use-sigstore-attachments: true\nEOF"
    )
    # The image's own policy is unchanged: everything rejected except AEGIS-signed images.
    policy = json.loads(vm.ssh("cat /etc/containers/policy.json").stdout)
    assert policy["default"] == [{"type": "reject"}]
    rule = policy["transports"]["docker"]["ghcr.io/ben10-games/aegis-os"][0]
    assert rule["type"] == "sigstoreSigned"


@pytest.mark.parametrize(
    "reference",
    [f"{REPOSITORY}:unsigned", f"{UNTRUSTED_REPOSITORY}:b"],
    ids=["unsigned", "untrusted-key"],
)
def test_unsigned_and_untrusted_updates_are_refused(vm, logdir, reference):
    result = vm.ssh(f"bootc switch {reference}", check=False, timeout=SWITCH_TIMEOUT_S)
    message = result.stdout + result.stderr
    log(logdir, "update", f"bootc switch {reference}: exit {result.returncode}\n{message[-1200:]}")
    assert result.returncode != 0, f"bootc accepted {reference}"
    assert any(word in message for word in ("signature", "policy", "ejected")), message[-1500:]
    assert bootc_status(vm)["status"].get("staged") is None, "something was staged"
    assert running_digest(vm) == sealed_digest("v3")


def test_signed_update_to_b_keeps_everything(vm, logdir):
    started = time.monotonic()
    result = vm.ssh(f"bootc switch {REPOSITORY}:b", check=False, timeout=SWITCH_TIMEOUT_S)
    log(
        logdir,
        "update",
        f"bootc switch {REPOSITORY}:b: exit {result.returncode} after "
        f"{time.monotonic() - started:.0f} s\n{(result.stdout + result.stderr)[-1500:]}",
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert bootc_status(vm)["status"].get("staged") is not None, "nothing was staged"
    reboot(vm)
    log(logdir, "update", "after the update:\n" + vm.ssh("bootc status").stdout)
    assert vm.ssh("cat /usr/share/aegis/update-marker").stdout.strip()
    log_in_at_greeter(vm, logdir, "update-b")
    assert_user_state(vm, logdir, "B after the update")
    chrome_starts(vm, logdir, "update-b")
    assert_system(vm, logdir, "B", "v3-update")
    shot(vm, logdir, "update-b-desktop")


def test_rollback_to_a_keeps_everything(vm, logdir):
    result = vm.ssh("bootc rollback", check=False, timeout=300)
    log(logdir, "update", f"bootc rollback: exit {result.returncode}\n{result.stderr[-800:]}")
    assert result.returncode == 0, result.stderr[-2000:]
    reboot(vm)
    log(logdir, "update", "after the rollback:\n" + vm.ssh("bootc status").stdout)
    assert vm.ssh("test -e /usr/share/aegis/update-marker", check=False).returncode != 0
    log_in_at_greeter(vm, logdir, "update-rollback")
    assert_user_state(vm, logdir, "A after the rollback")
    chrome_starts(vm, logdir, "update-rollback")
    assert_system(vm, logdir, "A after rollback", "v3")
    vm.ssh("systemctl poweroff", check=False)
    assert vm.wait_for_exit(180) == 0

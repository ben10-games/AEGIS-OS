"""Live ISO: rules for the live layer, the boot menu and the build (no image needed).

The live layer must keep the desktop account unprivileged, must not ship a password,
must leave SELinux and the AEGIS kernel arguments alone, and must change the sealed
images in no way (it is applied only in image/Containerfile.live).
"""

import re
import subprocess

import pytest

LIVE = "image/rootfs-live"


def test_live_account_is_unprivileged_and_has_no_password(root):
    sysusers = (root / LIVE / "usr/lib/sysusers.d/aegis-live.conf").read_text()
    entries = [line for line in sysusers.splitlines() if line and not line.startswith("#")]
    assert entries == ['u aegis 1000 "AEGIS Live user" /var/home/aegis /bin/bash']
    assert not list((root / LIVE).rglob("sudoers*"))
    for path in (root / LIVE).rglob("*"):
        if path.is_file():
            text = path.read_text(errors="replace")
            assert not re.search(r"\$[1256y]\$", text), f"{path}: contains a password hash"
            assert "NOPASSWD" not in text, path


def test_autologin_is_for_the_live_account_only(root):
    text = (root / LIVE / "etc/sddm.conf.d/50-aegis-live-autologin.conf").read_text()
    assert "User=aegis" in text and "Session=plasma.desktop" in text


def test_admin_password_is_random_per_boot_and_root_only(root):
    script = (root / LIVE / "usr/libexec/aegis/live-admin-password").read_text()
    assert "/dev/urandom" in script and "chpasswd" in script
    assert "umask 077" in script and 'chmod 0600 "${issue}.tmp"' in script
    unit = (root / LIVE / "usr/lib/systemd/system/aegis-live-admin.service").read_text()
    assert "ExecStart=/usr/libexec/aegis/live-admin-password" in unit


def test_live_admin_password_script_output(root, tmp_path):
    """Run the generator against a fake chpasswd: 4x4 characters, file mode 0600."""
    script = (root / LIVE / "usr/libexec/aegis/live-admin-password").read_text()
    script = script.replace("/etc/issue.d", str(tmp_path / "issue.d"))
    (tmp_path / "bin").mkdir()
    fake = tmp_path / "bin" / "chpasswd"
    fake.write_text(f"#!/bin/sh\ncat > {tmp_path}/chpasswd.in\n")
    fake.chmod(0o755)
    (tmp_path / "run").write_text(script)
    env = {"PATH": f"{tmp_path}/bin:/usr/bin:/bin"}
    subprocess.run(["bash", str(tmp_path / "run")], check=True, env=env, capture_output=True)
    issue = tmp_path / "issue.d" / "50-aegis-live-admin.issue"
    assert issue.stat().st_mode & 0o777 == 0o600
    password = re.search(r"password: (\S+)", issue.read_text()).group(1)
    assert re.fullmatch(r"([a-z0-9]{4}-){3}[a-z0-9]{4}", password)
    assert (tmp_path / "chpasswd.in").read_text() == f"root:{password}\n"
    subprocess.run(["bash", str(tmp_path / "run")], check=True, env=env, capture_output=True)
    assert password not in issue.read_text(), "the password must change at every boot"


def test_boot_menu_keeps_the_controls(root):
    menu = (root / "image/live/grub.cfg").read_text()
    assert "root=live:CDLABEL=@LABEL@" in menu and "@KARGS@" in menu
    for weakening in ("enforcing=0", "selinux=0", "lockdown=none", "init=/bin"):
        assert weakening not in menu


def test_live_containerfile_changes_only_the_live_root(root):
    text = (root / "image/Containerfile.live").read_text()
    assert "ARG BASE=localhost/aegis-gui-rootfs:latest" in text
    assert "COPY image/rootfs-live/ /" in text
    # The live layer is never copied into the sealed images.
    for name in ("Containerfile", "Containerfile.dev", "Containerfile.gui", "Containerfile.seal"):
        assert "rootfs-live" not in (root / "image" / name).read_text(), name


def test_iso_assembly_labels_and_keeps_xattrs(root):
    text = (root / "scripts/container/assemble-live-iso").read_text()
    assert "setfiles -F" in text and "-xattrs" in text
    assert "-e images/efiboot.img -no-emul-boot" in text


@pytest.mark.parametrize("path", ["scripts/build-live-iso", "scripts/container/assemble-live-iso"])
def test_live_build_never_writes_devices(root, path):
    text = (root / path).read_text()
    assert "/dev/sd" not in text and "/dev/nvme" not in text and "of=/dev" not in text

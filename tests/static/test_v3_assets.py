"""AEGIS OS v3 (M8): first-boot provisioning and release-image rules (no VM needed)."""

import importlib.util
import json
import re
import sys

import pytest

V3 = "image/rootfs-v3"


@pytest.fixture
def provision(root, tmp_path, monkeypatch):
    path = root / V3 / "usr/libexec/aegis/aegis_provision.py"
    spec = importlib.util.spec_from_file_location("aegis_provision", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    zones = tmp_path / "zoneinfo"
    (zones / "Europe").mkdir(parents=True)
    (zones / "Europe" / "Berlin").write_text("TZif")
    (zones / "UTC").write_text("TZif")
    monkeypatch.setattr(module, "ZONEINFO", zones)
    monkeypatch.setattr(module, "MARKER", tmp_path / "provisioned")
    monkeypatch.setattr(module, "AUTOLOGIN", tmp_path / "autologin.conf")
    return module


GOOD = {
    "full_name": "Alex Example",
    "user_name": "alex",
    "password": "correct horse battery",
    "administrator": True,
    "time_zone": "Europe/Berlin",
}


def test_a_valid_request_passes(provision):
    assert provision.validate(dict(GOOD)) == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_name", "root"),
        ("user_name", "aegis-setup"),
        ("user_name", "Alex"),
        ("user_name", "a b"),
        ("user_name", "x;id"),
        ("user_name", "-dash"),
        ("user_name", ""),
        ("password", "short"),
        ("password", "alex"),
        ("password", "line\nbreak!!"),
        ("password", None),
        ("full_name", ""),
        ("full_name", "a:b"),
        ("full_name", "a,b"),
        ("time_zone", "../../etc/passwd"),
        ("time_zone", "Mars/Olympus"),
        ("administrator", "yes"),
    ],
)
def test_invalid_requests_are_refused(provision, field, value):
    request = dict(GOOD)
    request[field] = value
    assert provision.validate(request) != ""


def test_requests_are_refused_once_provisioned(provision, monkeypatch, capsys):
    provision.MARKER.write_text("done")
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(GOOD) + "\n"))
    assert provision.main() == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer == {"ok": False, "message": "This computer is already set up."}


def test_password_reaches_chpasswd_on_stdin_only(root):
    source = (root / V3 / "usr/libexec/aegis/aegis_provision.py").read_text()
    assert "input=f\"{user_name}:{request['password']}\\n\"" in source
    assert "print(" not in source.split("def create")[1].split("def main")[0]


def test_setup_socket_is_restricted_and_one_shot(root):
    socket = (root / V3 / "usr/lib/systemd/system/aegis-provision.socket").read_text()
    assert "SocketGroup=aegis-setup" in socket and "SocketMode=0660" in socket
    assert "ConditionPathExists=!/var/lib/aegis/provisioned" in socket
    sysusers = (root / V3 / "usr/lib/sysusers.d/aegis-setup.conf").read_text()
    assert re.search(r"^u aegis-setup - ", sysusers, re.M), "must be a system account"


def test_release_image_has_no_development_access(root):
    containerfile = (root / "image/Containerfile.v3").read_text()
    assert "systemctl disable sshd.service" in containerfile
    assert "! systemctl is-enabled sshd.service" in containerfile
    assert "test ! -e /root/.ssh/authorized_keys" in containerfile
    assert "COPY image/rootfs/usr/lib/firewalld/zones/aegis.xml" in containerfile
    zone = (root / "image/rootfs/usr/lib/firewalld/zones/aegis.xml").read_text()
    assert '<service name="ssh"' not in zone
    for path in (root / V3).rglob("*"):
        if path.is_file():
            text = path.read_text(errors="replace")
            assert not re.search(r"\$(1|5|6|y|gy)\$", text), f"{path}: password hash"
            assert "PRIVATE KEY" not in text, path

"""The Linux launcher for local testing, run against a fake QEMU (needs no virtualization).

These tests pin the safety properties LOCAL_VM_GUIDE.md promises: the virtual machine
receives the image file and nothing else from the host, the SSH port is bound to the
loopback interface, and login is granted by launch-time credentials only.
"""

import base64
import subprocess

import pytest

PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIexampleexampleexampleexampleexampleexample me"


AUTOLOGIN_DROPIN = (
    "[Service]\n"
    "ExecStart=\n"
    "ExecStart=-/sbin/agetty --autologin root --noclear"
    " --keep-baud 115200,57600,38400,9600 - $TERM\n"
)


@pytest.fixture
def sandbox(tmp_path, root):
    """A fake qemu-system-x86_64 that records its arguments, plus image and firmware files."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "qemu-system-x86_64"
    fake.write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' "$@" > "${FAKE_QEMU_ARGS}"\n')
    fake.chmod(0o755)
    image = tmp_path / "aegis.qcow2"
    image.write_bytes(b"not really an image")
    code = tmp_path / "code.fd"
    code.touch()
    variables = tmp_path / "vars.fd"
    variables.write_bytes(b"template")
    key = tmp_path / "id.pub"
    key.write_text(PUBLIC_KEY + "\n")

    def run(*options, image_path=image):
        args_file = tmp_path / "args.txt"
        args_file.unlink(missing_ok=True)
        result = subprocess.run(
            [
                str(root / "local-vm" / "run-aegis-vm.sh"),
                "--image",
                str(image_path),
                "--firmware-code",
                str(code),
                "--firmware-vars",
                str(variables),
                "--accel",
                "tcg",
                *options,
            ],
            env={
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "FAKE_QEMU_ARGS": str(args_file),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        args = args_file.read_text().splitlines() if args_file.exists() else None
        return result, args

    return {"run": run, "image": image, "code": code, "key": key, "dir": tmp_path}


def values(args, option):
    return [args[i + 1] for i, arg in enumerate(args) if arg == option]


def test_only_the_image_and_the_firmware_are_attached(sandbox):
    result, args = sandbox["run"]()
    assert result.returncode == 0, result.stderr
    drives = values(args, "-drive")
    assert len(drives) == 3
    assert drives[0] == f"if=pflash,unit=0,format=raw,readonly=on,file={sandbox['code']}"
    assert drives[1] == f"if=pflash,unit=1,format=raw,file={sandbox['image']}.uefi-vars.fd"
    assert drives[2] == f"if=virtio,format=qcow2,file={sandbox['image']}"
    # No other way to reach host storage or devices is configured.
    assert "-nodefaults" in args
    forbidden = {"-hda", "-hdb", "-cdrom", "-virtfs", "-fsdev", "-usb", "-blockdev"}
    assert not forbidden & set(args)
    assert not [d for d in values(args, "-device") if "usb-host" in d or "vfio" in d]
    assert not any("/dev/" in arg for arg in args)


def test_firmware_variables_are_a_private_copy(sandbox):
    sandbox["run"]()
    copy = sandbox["dir"] / "aegis.qcow2.uefi-vars.fd"
    assert copy.read_bytes() == b"template"


@pytest.mark.parametrize("target", ["/dev/null", "/dev/loop0", "/"])
def test_devices_and_directories_are_refused(sandbox, target):
    result, args = sandbox["run"](image_path=target)
    assert result.returncode != 0
    assert "not a regular file" in result.stderr
    assert args is None, "QEMU must not be started"


def test_ssh_is_forwarded_on_loopback_only(sandbox):
    _, args = sandbox["run"]("--ssh-port", "2233")
    assert values(args, "-netdev") == ["user,id=net0,hostfwd=tcp:127.0.0.1:2233-:22"]


def test_login_is_granted_by_launch_time_credentials_only(sandbox):
    _, args = sandbox["run"]("--ssh-key", str(sandbox["key"]))
    smbios = values(args, "-smbios")
    autologin = (
        "type=11,value=io.systemd.credential.binary:systemd.unit-dropin.serial-getty@ttyS0.service="
    )
    dropin = base64.b64decode(next(v[len(autologin) :] for v in smbios if v.startswith(autologin)))
    assert dropin.decode() == AUTOLOGIN_DROPIN
    prefix = "type=11,value=io.systemd.credential.binary:ssh.authorized_keys.root="
    encoded = next(v[len(prefix) :] for v in smbios if v.startswith(prefix))
    assert base64.b64decode(encoded).decode() == PUBLIC_KEY + "\n"

    _, args = sandbox["run"]("--no-autologin")
    assert values(args, "-smbios") == []


def test_a_private_key_is_refused(sandbox):
    private = sandbox["dir"] / "id"
    private.write_text("-----BEGIN OPENSSH " + "PRIVATE KEY" + "-----\n")
    result, args = sandbox["run"]("--ssh-key", str(private))
    assert result.returncode != 0
    assert "PUBLIC" in result.stderr
    assert args is None


def test_snapshot_mode_and_commas_in_file_names(sandbox):
    odd = sandbox["dir"] / "a,b.qcow2"
    odd.write_bytes(b"x")
    _, args = sandbox["run"]("--snapshot", image_path=odd)
    assert "-snapshot" in args
    assert values(args, "-drive")[2].endswith("file=" + str(odd).replace(",", ",,"))


def test_both_launchers_pass_the_same_autologin_dropin(root):
    """The PowerShell launcher cannot be run here; its drop-in text is compared instead."""
    text = (root / "local-vm" / "run-aegis-vm.ps1").read_text()
    powershell = AUTOLOGIN_DROPIN.replace("\n", "`n").replace("$TERM", "`$TERM")
    assert f'$dropin = "{powershell}"' in text
    assert "systemd.unit-dropin.serial-getty@ttyS0.service=$dropinBase64" in text


def test_launchers_contain_no_password(root):
    for name in ("run-aegis-vm.sh", "run-aegis-vm.ps1"):
        text = (root / "local-vm" / name).read_text().lower()
        assert "passwd" not in text
        assert "password=" not in text
        assert "physicaldrive" not in text

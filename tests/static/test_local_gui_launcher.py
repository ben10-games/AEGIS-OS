"""GUI v1: the Linux launcher for the graphical image, run against a fake QEMU.

These tests pin what LOCAL_GUI_VM_GUIDE.md promises: the virtual machine receives the
image file and nothing else from the host, SSH is bound to loopback, the password never
appears on the QEMU command line (only its SHA-512 crypt hash), and the account the
launcher creates is the documented one.
"""

import base64
import subprocess

import pytest


@pytest.fixture
def sandbox(tmp_path, root):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "qemu-system-x86_64"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'case "$*" in\n'
        '  "-display help") echo gtk; echo sdl; echo none ;;\n'
        '  "-audiodev help") echo none; echo pa; echo alsa ;;\n'
        '  *) printf \'%s\\n\' "$@" > "${FAKE_QEMU_ARGS}" ;;\n'
        "esac\n"
    )
    fake.chmod(0o755)
    image = tmp_path / "aegis-os-gui.qcow2"
    image.write_bytes(b"not really an image")
    code = tmp_path / "code.fd"
    code.touch()
    variables = tmp_path / "vars.fd"
    variables.write_bytes(b"template")

    def run(*options, image_path=image):
        args_file = tmp_path / "args.txt"
        args_file.unlink(missing_ok=True)
        result = subprocess.run(
            [
                str(root / "local-vm" / "run-aegis-gui-vm.sh"),
                "--image",
                str(image_path),
                "--firmware-code",
                str(code),
                "--firmware-vars",
                str(variables),
                "--accel",
                "kvm",
                *options,
            ],
            env={"PATH": f"{bin_dir}:/usr/bin:/bin", "FAKE_QEMU_ARGS": str(args_file)},
            capture_output=True,
            text=True,
            check=False,
        )
        args = args_file.read_text().splitlines() if args_file.exists() else None
        return result, args

    return {"run": run, "image": image, "code": code, "dir": tmp_path}


def values(args, option):
    return [args[i + 1] for i, arg in enumerate(args) if arg == option]


def credentials(args):
    found = {}
    for value in values(args, "-smbios"):
        prefix = "type=11,value=io.systemd.credential.binary:"
        assert value.startswith(prefix), value
        name, _, encoded = value[len(prefix) :].partition("=")
        found[name] = base64.b64decode(encoded).decode()
    return found


def test_only_the_image_and_the_firmware_are_attached(sandbox):
    result, args = sandbox["run"]()
    assert result.returncode == 0, result.stderr
    drives = values(args, "-drive")
    assert len(drives) == 3
    assert drives[0].startswith("if=pflash,unit=0,format=raw,readonly=on,")
    assert drives[2] == f"if=virtio,format=qcow2,file={sandbox['image']}"
    assert "-nodefaults" in args
    forbidden = {"-hda", "-hdb", "-cdrom", "-virtfs", "-fsdev", "-blockdev", "-usbdevice"}
    assert not forbidden & set(args)
    devices = values(args, "-device")
    assert not [d for d in devices if "usb-host" in d or "vfio" in d or "usb-storage" in d]
    assert not any("/dev/" in arg for arg in args)


def test_graphics_input_and_sound_devices(sandbox):
    _, args = sandbox["run"]()
    devices = values(args, "-device")
    assert "virtio-vga,xres=1920,yres=1080" in devices
    assert {"qemu-xhci", "usb-kbd", "usb-tablet", "ich9-intel-hda"} <= set(devices)
    assert values(args, "-audiodev") == ["pa,id=snd0"]
    assert values(args, "-display") == ["gtk"]
    _, args = sandbox["run"]("--resolution", "2560x1440", "--audio", "none", "--display", "sdl")
    assert "virtio-vga,xres=2560,yres=1440" in values(args, "-device")
    assert values(args, "-audiodev") == ["none,id=snd0"]
    assert values(args, "-display") == ["sdl"]


def test_ssh_is_forwarded_on_loopback_only(sandbox):
    _, args = sandbox["run"]("--ssh-port", "2233")
    assert values(args, "-netdev") == ["user,id=net0,hostfwd=tcp:127.0.0.1:2233-:22"]


def test_the_account_and_only_a_password_hash(sandbox):
    result, args = sandbox["run"]()
    password = (sandbox["dir"] / "aegis-os-gui.qcow2.password").read_text().strip()
    assert len(password) == 16
    assert (sandbox["dir"] / "aegis-os-gui.qcow2.password").stat().st_mode & 0o077 == 0
    assert all(password not in arg for arg in args), "the password is on the command line"
    found = credentials(args)
    assert found["sysusers.extra"] == (
        'u aegis 1000 "AEGIS developer" /var/home/aegis /bin/bash\nm aegis wheel\n'
    )
    assert found["passwd.hashed-password.aegis"].startswith("$6$")
    assert "Autologin]\\nUser=aegis\\nSession=plasma.desktop" in found["tmpfiles.extra"]
    # The same password is kept for the next start of this image.
    sandbox["run"]()
    assert (sandbox["dir"] / "aegis-os-gui.qcow2.password").read_text().strip() == password


def test_no_admin_and_no_autologin(sandbox):
    _, args = sandbox["run"]("--no-admin", "--no-autologin", "--user", "dev")
    found = credentials(args)
    assert found["sysusers.extra"] == 'u dev 1000 "AEGIS developer" /var/home/dev /bin/bash\n'
    assert "Autologin" not in found["tmpfiles.extra"]


@pytest.mark.parametrize("target", ["/dev/null", "/dev/loop0", "/"])
def test_devices_and_directories_are_refused(sandbox, target):
    result, args = sandbox["run"](image_path=target)
    assert result.returncode != 0
    assert "refusing" in result.stderr
    assert args is None, "QEMU must not be started"


def test_only_qcow2_files_are_accepted(sandbox):
    raw = sandbox["dir"] / "disk.raw"
    raw.write_bytes(b"x")
    result, args = sandbox["run"](image_path=raw)
    assert result.returncode != 0 and args is None


@pytest.mark.parametrize("user", ["root", "Bad", "a b", "x;id"])
def test_bad_user_names_are_refused(sandbox, user):
    result, args = sandbox["run"]("--user", user)
    assert result.returncode != 0 and args is None


def test_a_private_key_is_refused(sandbox):
    private = sandbox["dir"] / "id"
    private.write_text("-----BEGIN OPENSSH " + "PRIVATE KEY" + "-----\n")
    result, args = sandbox["run"]("--ssh-key", str(private))
    assert result.returncode != 0 and args is None


def test_snapshot_mode(sandbox):
    _, args = sandbox["run"]("--snapshot")
    assert "-snapshot" in args

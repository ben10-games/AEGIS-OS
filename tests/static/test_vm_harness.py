"""Unit tests for the VM harness logic that needs no QEMU (runs in any environment)."""

import base64
from pathlib import Path

import pytest
from harness.qemu import HarnessError, VmConfig, build_qemu_command, find_firmware, pflash_format

KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIexampleexampleexampleexampleexampleexample test"


def config(**overrides) -> VmConfig:
    values = {
        "disk": Path("/scratch/disk.qcow2"),
        "firmware_code": Path("/fw/OVMF_CODE.fd"),
        "firmware_vars": Path("/scratch/vars.fd"),
        "ssh_port": 2222,
        "serial_log": Path("/logs/serial.log"),
        "authorized_key": KEY,
    }
    values.update(overrides)
    return VmConfig(**values)


def test_kvm_command_uses_host_cpu_and_forwards_ssh():
    command = build_qemu_command(config())
    assert "q35,accel=kvm" in command
    assert command[command.index("-cpu") + 1] == "host"
    assert "user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22" in command
    assert "file:/logs/serial.log" in command


def test_probe_port_is_forwarded_only_when_requested():
    assert (
        "hostfwd=tcp:127.0.0.1:2222-:22"
        in build_qemu_command(config())[build_qemu_command(config()).index("-netdev") + 1]
    )
    command = build_qemu_command(config(probe_port=18080))
    netdev = command[command.index("-netdev") + 1]
    assert netdev.endswith("hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:127.0.0.1:18080-:8080")


def test_tcg_command_does_not_require_kvm():
    command = build_qemu_command(config(accel="tcg"))
    assert "q35,accel=tcg" in command
    assert command[command.index("-cpu") + 1] == "max"


def test_unknown_accelerator_is_rejected():
    with pytest.raises(HarnessError):
        build_qemu_command(config(accel="xen"))


def test_secure_boot_needs_smm_and_protected_flash():
    plain = build_qemu_command(config())
    assert "q35,accel=kvm" in plain
    assert "-global" not in plain
    secure = build_qemu_command(config(secure_boot=True))
    assert "q35,accel=kvm,smm=on" in secure
    assert secure[secure.index("-global") + 1] == "driver=cfi.pflash01,property=secure,value=on"


def test_without_a_key_no_credential_reaches_the_guest():
    """Production-like machines get nothing from the harness but their disk."""
    assert "-smbios" not in build_qemu_command(config(authorized_key=""))


def test_extra_firmware_strings_are_passed_and_commas_refused():
    command = build_qemu_command(
        config(authorized_key="", smbios_strings=("io.systemd.stub.kernel-cmdline-extra=x=1",))
    )
    assert command[command.index("-smbios") + 1] == (
        "type=11,value=io.systemd.stub.kernel-cmdline-extra=x=1"
    )
    with pytest.raises(HarnessError):
        build_qemu_command(config(smbios_strings=("a,b",)))


def test_keys_are_enrolled_without_vendor_keys(tmp_path):
    from harness.firmware import SecureBootKeys, enrol_command

    for name in ("PK.crt", "KEK.crt", "db.crt"):
        (tmp_path / name).touch()
    (tmp_path / "owner-guid.txt").write_text("11111111-2222-3333-4444-555555555555\n")
    keys = SecureBootKeys.from_directory(tmp_path)
    command = enrol_command(Path("/fw/OVMF_VARS.fd"), Path("/scratch/vars.fd"), keys)
    assert command[0] == "virt-fw-vars"
    assert "--secure-boot" in command
    assert command[command.index("--set-pk") + 1 :][:2] == [
        keys.owner_guid,
        str(tmp_path / "PK.crt"),
    ]
    assert command[command.index("--add-db") + 2] == str(tmp_path / "db.crt")
    options = {arg for arg in command if arg.startswith("--")}
    assert options == {"--input", "--output", "--set-pk", "--add-kek", "--add-db", "--secure-boot"}


def test_ssh_key_is_passed_as_a_systemd_credential_not_written_to_disk():
    command = build_qemu_command(config())
    smbios = command[command.index("-smbios") + 1]
    prefix = "type=11,value=io.systemd.credential.binary:ssh.authorized_keys.root="
    assert smbios.startswith(prefix)
    encoded = smbios[len(prefix) :]
    assert "," not in encoded, "a comma would be parsed by QEMU as an option separator"
    assert base64.b64decode(encoded).decode() == KEY + "\n"


def test_firmware_is_read_only_and_variables_are_a_private_copy():
    command = build_qemu_command(config())
    drives = [command[i + 1] for i, arg in enumerate(command) if arg == "-drive"]
    code = next(d for d in drives if "OVMF_CODE.fd" in d)
    variables = next(d for d in drives if "vars.fd" in d)
    assert "readonly=on" in code
    assert "readonly=on" not in variables
    assert "file=/scratch/vars.fd" in variables


def test_pflash_format_follows_file_suffix():
    assert pflash_format(Path("OVMF_CODE.fd")) == "raw"
    assert pflash_format(Path("OVMF_CODE_4M.qcow2")) == "qcow2"


def test_find_firmware_returns_first_complete_pair(tmp_path):
    incomplete = (str(tmp_path / "a_code.fd"), str(tmp_path / "a_vars.fd"))
    complete = (str(tmp_path / "b_code.fd"), str(tmp_path / "b_vars.fd"))
    Path(incomplete[0]).touch()  # code present, variables missing
    Path(complete[0]).touch()
    Path(complete[1]).touch()
    assert find_firmware((incomplete, complete)) == (Path(complete[0]), Path(complete[1]))


def test_find_firmware_reports_what_it_looked_for(tmp_path):
    missing = (str(tmp_path / "none_code.fd"), str(tmp_path / "none_vars.fd"))
    with pytest.raises(HarnessError, match="none_code.fd"):
        find_firmware((missing,))

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


def test_tcg_command_does_not_require_kvm():
    command = build_qemu_command(config(accel="tcg"))
    assert "q35,accel=tcg" in command
    assert command[command.index("-cpu") + 1] == "max"


def test_unknown_accelerator_is_rejected():
    with pytest.raises(HarnessError):
        build_qemu_command(config(accel="xen"))


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

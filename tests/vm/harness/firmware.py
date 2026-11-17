"""UEFI firmware with Secure Boot for test virtual machines.

The firmware code is the Secure Boot build of OVMF. Its variable store starts empty
("setup mode"), and `enrol_command` writes the project's throw-away PK, KEK and db
certificates into a private copy and switches Secure Boot on. From then on the
firmware refuses every EFI binary that is not signed by the db key.

Building the command line is a pure function so it can be unit-tested without the tool.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# (code, empty variable store) pairs of Secure Boot capable firmware, in order of preference.
SECURE_BOOT_FIRMWARE: tuple[tuple[str, str], ...] = (
    ("/usr/share/edk2/ovmf/OVMF_CODE.secboot.fd", "/usr/share/edk2/ovmf/OVMF_VARS.fd"),
    ("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
    ("/usr/share/OVMF/OVMF_CODE.secboot.fd", "/usr/share/OVMF/OVMF_VARS.fd"),
)

# QEMU settings the Secure Boot build of OVMF requires: it keeps its variables behind
# System Management Mode, so that the guest operating system cannot rewrite them.
SECURE_BOOT_MACHINE_OPTIONS = "smm=on"
SECURE_BOOT_GLOBALS = ("driver=cfi.pflash01,property=secure,value=on",)


class FirmwareError(RuntimeError):
    """Secure Boot firmware could not be found or prepared."""


@dataclass(frozen=True)
class SecureBootKeys:
    """Public halves of the throw-away key hierarchy made by scripts/dev-keys."""

    pk: Path
    kek: Path
    db: Path
    owner_guid: str

    @classmethod
    def from_directory(cls, directory: Path) -> SecureBootKeys:
        missing = [
            name
            for name in ("PK.crt", "KEK.crt", "db.crt", "owner-guid.txt")
            if not (directory / name).is_file()
        ]
        if missing:
            raise FirmwareError(
                f"{directory} lacks {missing}; the image build writes them (scripts/build-image)"
            )
        return cls(
            pk=directory / "PK.crt",
            kek=directory / "KEK.crt",
            db=directory / "db.crt",
            owner_guid=(directory / "owner-guid.txt").read_text().strip(),
        )


def find_secure_boot_firmware(candidates=SECURE_BOOT_FIRMWARE) -> tuple[Path, Path]:
    for code, variables in candidates:
        if Path(code).is_file() and Path(variables).is_file():
            return Path(code), Path(variables)
    tried = ", ".join(code for code, _ in candidates)
    raise FirmwareError(f"no Secure Boot firmware found; looked for: {tried}")


def enrol_command(template: Path, output: Path, keys: SecureBootKeys) -> list[str]:
    """virt-fw-vars call that enrols the keys and enables Secure Boot. No vendor keys."""
    return [
        "virt-fw-vars",
        "--input", str(template),
        "--output", str(output),
        "--set-pk", keys.owner_guid, str(keys.pk),
        "--add-kek", keys.owner_guid, str(keys.kek),
        "--add-db", keys.owner_guid, str(keys.db),
        "--secure-boot",
    ]  # fmt: skip


def enrol_keys(template: Path, output: Path, keys: SecureBootKeys) -> str:
    """Write a variable store with the keys enrolled; return the tool's report."""
    result = subprocess.run(
        enrol_command(template, output, keys), capture_output=True, text=True, check=False
    )
    report = result.stdout + result.stderr
    if result.returncode != 0 or not output.is_file():
        raise FirmwareError(f"virt-fw-vars failed ({result.returncode}):\n{report}")
    return report

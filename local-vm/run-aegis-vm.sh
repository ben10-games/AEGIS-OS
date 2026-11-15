#!/usr/bin/env bash
# Start the AEGIS OS development image in QEMU on Linux.
#
#   ./run-aegis-vm.sh --image aegis-os-dev.qcow2 [options]
#
# The virtual machine can only reach the image file given here. No host disk, partition
# or folder is attached, and networking is QEMU's user-mode network (no changes to the
# host's network configuration). Nothing is installed on the host.
#
# Login: the image contains no password and no key. This script passes two systemd
# credentials through the virtual firmware, and only for this run:
#   - a drop-in for the serial console's login service that logs root in automatically
#     (the serial console is this terminal)
#   - your SSH public key, if you give one with --ssh-key
set -euo pipefail

image=""
ssh_key=""
ssh_port=2222
memory=4096
cpus=2
accel=""
snapshot=0
autologin=1
firmware_code=""
firmware_vars=""
serial="mon:stdio"

usage() {
  cat <<'USAGE'
Usage: run-aegis-vm.sh --image FILE [options]

  --image FILE          the downloaded .qcow2 image (required)
  --ssh-key FILE        SSH public key to allow for root (for example ~/.ssh/id_ed25519.pub)
  --ssh-port PORT       host port forwarded to the guest's SSH port (default 2222)
  --memory MIB          guest memory in MiB (default 4096, minimum 2048)
  --cpus N              guest CPUs (default 2)
  --accel kvm|tcg       acceleration (default: kvm if /dev/kvm is usable, else tcg)
  --snapshot            discard every change to the image when the VM stops
  --no-autologin        do not log in automatically on the serial console
  --firmware-code FILE  UEFI firmware code (default: searched in the usual locations)
  --firmware-vars FILE  UEFI variable store template
  --serial SPEC         QEMU serial backend (default mon:stdio; used by automated tests)

Leave the console: press Ctrl-A then X. Shut down cleanly: run 'poweroff' in the guest.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) image="$2"; shift 2 ;;
    --ssh-key) ssh_key="$2"; shift 2 ;;
    --ssh-port) ssh_port="$2"; shift 2 ;;
    --memory) memory="$2"; shift 2 ;;
    --cpus) cpus="$2"; shift 2 ;;
    --accel) accel="$2"; shift 2 ;;
    --snapshot) snapshot=1; shift ;;
    --no-autologin) autologin=0; shift ;;
    --firmware-code) firmware_code="$2"; shift 2 ;;
    --firmware-vars) firmware_vars="$2"; shift 2 ;;
    --serial) serial="$2"; shift 2 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "error: unknown option '$1'" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${image}" ]]; then
  echo "error: --image is required" >&2
  usage >&2
  exit 2
fi
# Safety: only a regular file is ever handed to the virtual machine.
if [[ ! -f "${image}" || -b "${image}" ]]; then
  echo "error: '${image}' is not a regular file; refusing to use it" >&2
  exit 1
fi
if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo "error: qemu-system-x86_64 not found; install QEMU with your package manager" >&2
  exit 1
fi

if [[ -z "${accel}" ]]; then
  if [[ -r /dev/kvm && -w /dev/kvm ]]; then accel=kvm; else accel=tcg; fi
fi
if [[ "${accel}" == "kvm" ]]; then cpu=host; else cpu=max; fi
if [[ "${accel}" == "tcg" ]]; then
  echo "note: no KVM acceleration; the VM runs in software emulation and is much slower" >&2
fi

# UEFI firmware (OVMF). Different distributions install it in different places.
if [[ -z "${firmware_code}" ]]; then
  while read -r code vars; do
    if [[ -f "${code}" && -f "${vars}" ]]; then
      firmware_code="${code}"
      firmware_vars="${vars}"
      break
    fi
  done <<'FIRMWARE'
/usr/share/edk2/ovmf/OVMF_CODE.fd /usr/share/edk2/ovmf/OVMF_VARS.fd
/usr/share/edk2/ovmf/OVMF_CODE_4M.qcow2 /usr/share/edk2/ovmf/OVMF_VARS_4M.qcow2
/usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_VARS_4M.fd
/usr/share/OVMF/OVMF_CODE.fd /usr/share/OVMF/OVMF_VARS.fd
/usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/edk2/x64/OVMF_VARS.4m.fd
/usr/share/edk2-ovmf/x64/OVMF_CODE.fd /usr/share/edk2-ovmf/x64/OVMF_VARS.fd
/usr/share/qemu/ovmf-x86_64-code.bin /usr/share/qemu/ovmf-x86_64-vars.bin
FIRMWARE
fi
if [[ -z "${firmware_code}" || ! -f "${firmware_code}" || ! -f "${firmware_vars}" ]]; then
  echo "error: UEFI firmware (OVMF) not found; install the 'edk2-ovmf' or 'ovmf' package," >&2
  echo "       or pass --firmware-code and --firmware-vars" >&2
  exit 1
fi

# Firmware files are raw (.fd, .bin) or, on newer Fedora, QCOW2.
pflash_format() {
  if [[ "$1" == *.qcow2 ]]; then echo qcow2; else echo raw; fi
}
# QEMU splits option values at commas; a comma inside a file name is written twice.
escaped() {
  printf '%s' "${1//,/,,}"
}

# The firmware needs a writable variable store; keep a private copy next to the image.
vars_copy="${image}.uefi-vars.${firmware_vars##*.}"
if [[ ! -f "${vars_copy}" ]]; then
  cp "${firmware_vars}" "${vars_copy}"
fi

# shellcheck disable=SC2054 # the commas belong to QEMU's option syntax
args=(
  -machine "q35,accel=${accel}"
  -cpu "${cpu}"
  -smp "${cpus}"
  -m "${memory}"
  -drive "if=pflash,unit=0,format=$(pflash_format "${firmware_code}"),readonly=on,file=$(escaped "${firmware_code}")"
  -drive "if=pflash,unit=1,format=$(pflash_format "${vars_copy}"),file=$(escaped "${vars_copy}")"
  -drive "if=virtio,format=qcow2,file=$(escaped "${image}")"
  -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:${ssh_port}-:22"
  -device virtio-net-pci,netdev=net0
  -device virtio-rng-pci
  -display none
  -serial "${serial}"
  -nodefaults
)
if [[ "${snapshot}" -eq 1 ]]; then
  args+=(-snapshot)
fi
if [[ "${autologin}" -eq 1 ]]; then
  # systemd turns this credential into a drop-in for serial-getty@ttyS0.service.
  dropin=$'[Service]\nExecStart=\nExecStart=-/sbin/agetty --autologin root --noclear --keep-baud 115200,57600,38400,9600 - $TERM\n'
  encoded="$(printf '%s' "${dropin}" | base64 -w0)"
  args+=(-smbios "type=11,value=io.systemd.credential.binary:systemd.unit-dropin.serial-getty@ttyS0.service=${encoded}")
fi
if [[ -n "${ssh_key}" ]]; then
  if [[ ! -f "${ssh_key}" ]] || grep -q "PRIVATE KEY" "${ssh_key}"; then
    echo "error: --ssh-key must be a PUBLIC key file (usually ending in .pub)" >&2
    exit 1
  fi
  key="$(base64 -w0 < "${ssh_key}")"
  args+=(-smbios "type=11,value=io.systemd.credential.binary:ssh.authorized_keys.root=${key}")
fi

echo "Starting AEGIS OS (${accel}, ${cpus} CPUs, ${memory} MiB). SSH: ssh -p ${ssh_port} root@127.0.0.1" >&2
exec qemu-system-x86_64 "${args[@]}"

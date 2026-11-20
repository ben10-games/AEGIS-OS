#!/usr/bin/env bash
# Start the AEGIS OS graphical development image (KDE Plasma 6 on Wayland) in QEMU on
# Linux, for example Linux Mint 21/22, Ubuntu, Debian or Fedora.
#
#   ./run-aegis-gui-vm.sh --image aegis-os-gui-<version>-<commit>.qcow2 [options]
#
# The virtual machine can only reach the image file given here. No host disk, partition,
# USB device or folder is attached, and networking is QEMU's user-mode network (no change
# to the host's network). Nothing is installed or changed on the host.
#
# Login: the image contains no user and no password. On its first start this script
# hands the guest, through the virtual firmware (systemd credentials), for this VM only:
#   - a user account (default 'aegis'), with a random password generated here and kept
#     in <image>.password next to the image (mode 600); the user is an administrator
#     (group wheel, sudo with that password) unless --no-admin is given,
#   - automatic desktop login for that user (switch off with --no-autologin),
#   - your SSH public key for root, if you give one with --ssh-key.
# The account is created on the first boot of a disk and then belongs to that disk; with
# --snapshot nothing is kept and the account is created again at every start.
set -euo pipefail

image=""
user_name="aegis"
password_file=""
admin=1
autologin=1
ssh_key=""
ssh_port=2222
memory=6144
cpus=4
accel=""
resolution="1920x1080"
display=""
gl=0
audio=""
snapshot=0
firmware_code=""
firmware_vars=""
serial=""
qmp=""
dry_run=0

usage() {
  cat <<'USAGE'
Usage: run-aegis-gui-vm.sh --image FILE [options]

  --image FILE          the downloaded aegis-os-gui .qcow2 image (required)
  --snapshot            discard every change to the image when the VM stops
  --memory MIB          guest memory in MiB (default 6144, minimum 4096)
  --cpus N              guest CPUs (default 4)
  --resolution WxH      display size (default 1920x1080)
  --display gtk|sdl|none
                        window toolkit (default: gtk if available, else sdl)
  --gl                  3D acceleration through the host GPU (virtio-vga-gl; needs a
                        working OpenGL driver on the host; not tested by the project)
  --audio pa|pipewire|alsa|none
                        host sound system (default: pa, which also serves PipeWire
                        hosts such as Linux Mint 21/22, if QEMU supports it, else none)
  --user NAME           desktop user to create on first boot (default aegis)
  --password-file FILE  file holding the password for that user (default: generated
                        once into IMAGE.password)
  --no-admin            the user is not an administrator (no sudo)
  --no-autologin        show the login screen instead of logging in automatically
  --ssh-key FILE        SSH public key to allow for root (for example ~/.ssh/id_ed25519.pub)
  --ssh-port PORT       host port (on 127.0.0.1 only) forwarded to the guest's SSH (default 2222)
  --accel kvm|tcg       acceleration (default: kvm if /dev/kvm is usable, else tcg)
  --firmware-code FILE  UEFI firmware code (default: searched in the usual locations)
  --firmware-vars FILE  UEFI variable store template
  --serial SPEC         QEMU serial backend (default: file IMAGE.serial.log)
  --qmp PATH            QEMU control socket (used by the project's automated tests)
  --dry-run             print the QEMU command line and exit

Shut down cleanly from the desktop (Leave > Shut Down) or with 'poweroff'.
USAGE
}

die() {
  echo "error: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) image="$2"; shift 2 ;;
    --snapshot) snapshot=1; shift ;;
    --memory) memory="$2"; shift 2 ;;
    --cpus) cpus="$2"; shift 2 ;;
    --resolution) resolution="$2"; shift 2 ;;
    --display) display="$2"; shift 2 ;;
    --gl) gl=1; shift ;;
    --audio) audio="$2"; shift 2 ;;
    --user) user_name="$2"; shift 2 ;;
    --password-file) password_file="$2"; shift 2 ;;
    --no-admin) admin=0; shift ;;
    --no-autologin) autologin=0; shift ;;
    --ssh-key) ssh_key="$2"; shift 2 ;;
    --ssh-port) ssh_port="$2"; shift 2 ;;
    --accel) accel="$2"; shift 2 ;;
    --firmware-code) firmware_code="$2"; shift 2 ;;
    --firmware-vars) firmware_vars="$2"; shift 2 ;;
    --serial) serial="$2"; shift 2 ;;
    --qmp) qmp="$2"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h | --help) usage; exit 0 ;;
    *) echo "error: unknown option '$1'" >&2; usage >&2; exit 2 ;;
  esac
done

# --- checks -----------------------------------------------------------------------------
[[ -n "${image}" ]] || { echo "error: --image is required" >&2; usage >&2; exit 2; }
# Safety: only a regular .qcow2 file is ever handed to the virtual machine, never a disk.
if [[ "${image}" == /dev/* || -b "${image}" || -c "${image}" || ! -f "${image}" ]]; then
  die "'${image}' is not a regular file; refusing to use it"
fi
[[ "${image}" == *.qcow2 ]] || die "'${image}' is not a .qcow2 image; refusing to use it"
[[ "${memory}" =~ ^[0-9]+$ && "${memory}" -ge 4096 ]] || die "--memory must be at least 4096"
[[ "${cpus}" =~ ^[0-9]+$ && "${cpus}" -ge 1 ]] || die "--cpus must be a positive number"
[[ "${resolution}" =~ ^([0-9]{3,4})x([0-9]{3,4})$ ]] || die "--resolution must look like 1920x1080"
xres="${BASH_REMATCH[1]}"
yres="${BASH_REMATCH[2]}"
[[ "${user_name}" =~ ^[a-z_][a-z0-9_-]{0,30}$ && "${user_name}" != root ]] \
  || die "--user must be a lower-case user name other than root"
[[ "${ssh_port}" =~ ^[0-9]+$ ]] || die "--ssh-port must be a number"

missing=()
command -v qemu-system-x86_64 > /dev/null 2>&1 || missing+=("qemu-system-x86_64 (package qemu-system-x86)")
command -v openssl > /dev/null 2>&1 || missing+=("openssl (package openssl)")
command -v base64 > /dev/null 2>&1 || missing+=("base64 (package coreutils)")
if [[ "${#missing[@]}" -gt 0 ]]; then
  echo "error: missing programs on this computer:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  echo "On Linux Mint / Ubuntu: sudo apt install qemu-system-x86 qemu-system-gui ovmf openssl" >&2
  exit 1
fi

if [[ -z "${accel}" ]]; then
  if [[ -r /dev/kvm && -w /dev/kvm ]]; then accel=kvm; else accel=tcg; fi
fi
case "${accel}" in
  kvm) cpu=host ;;
  tcg)
    cpu=max
    echo "note: no KVM acceleration (is your user in the 'kvm' group?); the desktop will be very slow" >&2
    ;;
  *) die "--accel must be kvm or tcg" ;;
esac

# Window toolkit: Ubuntu and Mint ship QEMU's GTK and SDL front ends in qemu-system-gui.
displays="$(qemu-system-x86_64 -display help 2>/dev/null || true)"
if [[ -z "${display}" ]]; then
  if grep -qw gtk <<< "${displays}"; then
    display=gtk
  elif grep -qw sdl <<< "${displays}"; then
    display=sdl
  else
    die "this QEMU has no window front end (gtk or sdl); on Linux Mint / Ubuntu install 'qemu-system-gui'"
  fi
fi
case "${display}" in
  gtk | sdl)
    grep -qw "${display}" <<< "${displays}" \
      || die "this QEMU has no '${display}' front end; install 'qemu-system-gui' or choose another --display"
    ;;
  none) ;;
  *) die "--display must be gtk, sdl or none" ;;
esac

audiodevs="$(qemu-system-x86_64 -audiodev help 2>/dev/null || true)"
if [[ -z "${audio}" ]]; then
  if grep -qw pa <<< "${audiodevs}"; then audio=pa; else audio=none; fi
fi
case "${audio}" in
  pa | pipewire | alsa)
    grep -qw "${audio}" <<< "${audiodevs}" || die "this QEMU has no '${audio}' sound back end; use --audio none"
    ;;
  none) ;;
  *) die "--audio must be pa, pipewire, alsa or none" ;;
esac

# UEFI firmware (OVMF) without Secure Boot keys. Linux Mint / Ubuntu: package 'ovmf'.
if [[ -z "${firmware_code}" ]]; then
  while read -r code vars; do
    if [[ -f "${code}" && -f "${vars}" ]]; then
      firmware_code="${code}"
      firmware_vars="${vars}"
      break
    fi
  done << 'FIRMWARE'
/usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_VARS_4M.fd
/usr/share/OVMF/OVMF_CODE.fd /usr/share/OVMF/OVMF_VARS.fd
/usr/share/edk2/ovmf/OVMF_CODE.fd /usr/share/edk2/ovmf/OVMF_VARS.fd
/usr/share/edk2/ovmf/OVMF_CODE_4M.qcow2 /usr/share/edk2/ovmf/OVMF_VARS_4M.qcow2
/usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/edk2/x64/OVMF_VARS.4m.fd
/usr/share/edk2-ovmf/x64/OVMF_CODE.fd /usr/share/edk2-ovmf/x64/OVMF_VARS.fd
/usr/share/qemu/ovmf-x86_64-code.bin /usr/share/qemu/ovmf-x86_64-vars.bin
FIRMWARE
fi
if [[ -z "${firmware_code}" || ! -f "${firmware_code}" || ! -f "${firmware_vars}" ]]; then
  die "UEFI firmware (OVMF) not found; on Linux Mint / Ubuntu install 'ovmf', or pass --firmware-code and --firmware-vars"
fi

pflash_format() {
  if [[ "$1" == *.qcow2 ]]; then echo qcow2; else echo raw; fi
}
# QEMU splits option values at commas; a comma inside a file name is written twice.
escaped() {
  printf '%s' "${1//,/,,}"
}
credential() { # name value
  printf 'type=11,value=io.systemd.credential.binary:%s=%s' "$1" "$(printf '%b' "$2" | base64 -w0)"
}

# --- the development login --------------------------------------------------------------
if [[ -z "${password_file}" ]]; then
  password_file="${image}.password"
  if [[ ! -s "${password_file}" ]]; then
    (umask 077 && openssl rand -base64 18 | tr -d '/+=\n' | cut -c1-16 > "${password_file}")
    echo "A password for '${user_name}' was generated and saved in ${password_file}" >&2
  fi
fi
[[ -s "${password_file}" ]] || die "password file '${password_file}' is empty or missing"
password="$(head -n 1 "${password_file}")"
[[ "${#password}" -ge 8 ]] || die "the password in '${password_file}' is shorter than 8 characters"
# Only the hash reaches the guest (and the QEMU command line).
hashed="$(printf '%s' "${password}" | openssl passwd -6 -stdin)"

home="/var/home/${user_name}"
# uid 1000: the first regular user (an automatic uid would be a system account).
sysusers="u ${user_name} 1000 \"AEGIS developer\" ${home} /bin/bash\n"
if [[ "${admin}" -eq 1 ]]; then
  sysusers+="m ${user_name} wheel\n"
fi
tmpfiles="d ${home} 0700 ${user_name} ${user_name} -\n"
if [[ "${autologin}" -eq 1 ]]; then
  tmpfiles+="f+ /etc/sddm.conf.d/50-aegis-launcher-autologin.conf 0644 root root - "
  tmpfiles+="[Autologin]\\\\nUser=${user_name}\\\\nSession=plasma.desktop\\\\nRelogin=false\\\\n\n"
fi

# The firmware needs a writable variable store; keep a private copy next to the image.
vars_copy="${image}.uefi-vars.${firmware_vars##*.}"
if [[ ! -f "${vars_copy}" ]]; then
  cp "${firmware_vars}" "${vars_copy}"
fi
[[ -n "${serial}" ]] || serial="file:${image}.serial.log"

if [[ "${gl}" -eq 1 ]]; then
  [[ "${display}" != none ]] || die "--gl needs a window (--display gtk or sdl)"
  gpu="virtio-vga-gl,xres=${xres},yres=${yres}"
  display_opt="${display},gl=on"
else
  gpu="virtio-vga,xres=${xres},yres=${yres}"
  display_opt="${display}"
fi

# shellcheck disable=SC2054 # the commas belong to QEMU's option syntax
args=(
  -name "AEGIS OS (graphical development image)"
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
  -device "${gpu}"
  -device qemu-xhci
  -device usb-kbd
  -device usb-tablet
  -audiodev "${audio},id=snd0"
  -device ich9-intel-hda
  -device hda-duplex,audiodev=snd0
  -display "${display_opt}"
  -serial "${serial}"
  -smbios "$(credential sysusers.extra "${sysusers}")"
  -smbios "$(credential "passwd.hashed-password.${user_name}" "${hashed}")"
  -smbios "$(credential tmpfiles.extra "${tmpfiles}")"
  -nodefaults
)
if [[ "${snapshot}" -eq 1 ]]; then
  args+=(-snapshot)
fi
if [[ -n "${qmp}" ]]; then
  args+=(-qmp "unix:$(escaped "${qmp}"),server=on,wait=off")
fi
if [[ -n "${ssh_key}" ]]; then
  if [[ ! -f "${ssh_key}" ]] || grep -q "PRIVATE KEY" "${ssh_key}"; then
    die "--ssh-key must be a PUBLIC key file (usually ending in .pub)"
  fi
  args+=(-smbios "type=11,value=io.systemd.credential.binary:ssh.authorized_keys.root=$(base64 -w0 < "${ssh_key}")")
fi

if [[ "${dry_run}" -eq 1 ]]; then
  printf '%s\n' qemu-system-x86_64 "${args[@]}"
  exit 0
fi

cat >&2 << EOF
Starting AEGIS OS (graphical development image): ${accel}, ${cpus} CPUs, ${memory} MiB, ${xres}x${yres}, display ${display_opt}, audio ${audio}$([[ "${snapshot}" -eq 1 ]] && echo ", snapshot mode")
  user:     ${user_name}$([[ "${admin}" -eq 1 ]] && echo " (administrator: sudo)")
  password: in ${password_file}
  console:  ${serial#file:}
  SSH:      ssh -p ${ssh_port} root@127.0.0.1 (only with --ssh-key)
Secure Boot is off in this VM: the firmware does not verify the boot chain here.
EOF
exec qemu-system-x86_64 "${args[@]}"

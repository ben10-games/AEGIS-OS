# AEGIS OS — running the graphical development image on Linux Mint

This guide takes you from download to a running AEGIS OS desktop (KDE Plasma 6 on
Wayland) in a virtual machine on your own Linux computer. It is written for **Linux
Mint 21 and 22**; Ubuntu 22.04/24.04 and Debian 12/13 work the same way. Fedora and Arch
users install the equivalent packages named in section 1.

**What you are testing.** `aegis-gui` is the *graphical development* variant of AEGIS OS:
the sealed, SELinux-enforcing AEGIS development image plus the KDE Plasma 6 desktop with
the AEGIS look. It is not a release. It includes an SSH server for development.

**What this cannot do to your computer.** The virtual machine receives exactly one thing:
the image file you downloaded. No physical disk, partition, USB device or folder of your
computer is attached; networking is QEMU's built-in user-mode network, so your network
settings are not changed. Nothing is installed by the launcher, and you do not need to
turn off any security setting of your computer. Deleting the folder removes everything.

## 1. What you need

| | Recommended | Minimum |
|---|---|---|
| CPU | x86-64 with virtualization enabled in the firmware (Intel VT-x / AMD-V), 4 cores for the VM | 2 cores (slow) |
| Memory for the VM | 6 GiB (the default) | 4 GiB |
| Free disk space | 20 GiB | 10 GiB |
| Display | 1920x1080 (the default size of the VM's screen) | any; the window can be resized |

Install QEMU, its window front end, the UEFI firmware and OpenSSL (used to hash the
login password). On Linux Mint / Ubuntu / Debian:

```bash
sudo apt install qemu-system-x86 qemu-system-gui ovmf openssl
```

Fedora: `sudo dnf install qemu-system-x86-core qemu-ui-gtk qemu-audio-pa edk2-ovmf openssl`.
Arch: `sudo pacman -S qemu-desktop edk2-ovmf openssl`.

For hardware acceleration your user needs access to `/dev/kvm`. On Linux Mint this
usually means membership of the `kvm` group:

```bash
sudo usermod -aG kvm "$USER"
```

Log out and in again afterwards. Without KVM the launcher still works, but the desktop is
very slow.

## 2. Download

1. Open the repository on GitHub → **Actions** → workflow **build** → a recent run with
   a green tick on branch `claude/aegis-os-gui-v1` that has an artifact named
   **`aegis-os-gui-qcow2`** (bottom of the run page). You must be signed in to GitHub.
2. Download it (a ZIP file of a few GB) and extract it into an empty folder.

GitHub deletes artifacts after 14 days. The folder contains:

| File | Purpose |
|---|---|
| `aegis-os-gui-<version>-<commit>.qcow2` | the disk image |
| `run-aegis-gui-vm.sh` | the launcher |
| `LOCAL_GUI_VM_GUIDE.md` | this guide |
| `IMAGE-INFO.txt` | what was built, from which commit and inputs |
| `SHA256SUMS` | checksums of all of the above |

## 3. Verify the download

In the extracted folder:

```bash
sha256sum -c SHA256SUMS
```

Every line must end in `OK`. This shows the files are complete and are the ones tested in
CI.

## 4. Start the desktop

```bash
chmod +x run-aegis-gui-vm.sh
```

```bash
./run-aegis-gui-vm.sh --image aegis-os-gui-*.qcow2
```

A window opens with the firmware, then the AEGIS desktop logs in by itself (about one
minute with KVM). The terminal shows the user name and where the password is stored.

To try something without keeping any change, add `--snapshot`: every change is thrown
away when the VM stops, and the next start is like the first.

Useful options (see `--help`):

| Option | Effect |
|---|---|
| `--snapshot` | discard all changes at shutdown |
| `--memory 8192`, `--cpus 6` | more memory or processors for the VM |
| `--resolution 2560x1440` | another screen size for the VM |
| `--display sdl` | use SDL instead of GTK for the window |
| `--audio none` | no sound (if QEMU reports a sound problem) |
| `--no-autologin` | show the login screen instead |
| `--no-admin` | the user cannot use `sudo` |
| `--ssh-key ~/.ssh/id_ed25519.pub` | SSH as root: `ssh -p 2222 root@127.0.0.1` (bound to your computer only) |
| `--gl` | 3D acceleration through your GPU (virtio-vga-gl); not tested by the project, needs a working OpenGL driver |

## 5. Logging in

The image contains **no user and no password**. On the first start the launcher:

1. creates a random password for the user **`aegis`** and saves it next to the image in
   `<image>.qcow2.password` (readable only by you),
2. hands the VM, through the virtual firmware, a request to create the user `aegis`
   (uid 1000, member of `wheel`, so `sudo` works with that password) with only the
   password's SHA-512 hash, and to log it in to the desktop automatically.

```bash
cat aegis-os-gui-*.qcow2.password
```

Use this password for `sudo`, for the lock screen, and at the login screen if you start
with `--no-autologin`. The account is created on the first boot of the disk and then
belongs to it. With `--snapshot` it is created again at every start. Root has no password
and cannot log in on the desktop.

This is a development mechanism: whoever can start the VM controls the account. A
release image will have a proper first-boot user setup instead.

## 6. Things to try

- The dock at the bottom: launcher (start menu), Files (Dolphin), Terminal (Konsole),
  System Settings. **Ctrl+Alt+T** opens a terminal.
- In the terminal:

  ```bash
  getenforce
  ```

  ```bash
  bootc status
  ```

  ```bash
  touch /usr/test
  ```

  Expected: `Enforcing`; the booted AEGIS image; "Read-only file system" (the operating
  system tree cannot be changed at runtime).
- System Settings → Display, Network, Sound, Appearance (AEGIS Dark colours).

## 7. Shutting down

Use the desktop (launcher → Leave → Shut Down) or run `poweroff` in a terminal. The
launcher returns when the VM has stopped. Closing the QEMU window is like pulling the
power cord.

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "missing programs on this computer" | Install the packages listed in section 1. |
| "this QEMU has no window front end" | `sudo apt install qemu-system-gui` |
| "UEFI firmware (OVMF) not found" | `sudo apt install ovmf`, or pass `--firmware-code` and `--firmware-vars` |
| "no KVM acceleration" and a very slow desktop | Enable virtualization in your computer's firmware setup and add your user to the `kvm` group (section 1). |
| QEMU reports an audio error | Start with `--audio none`. |
| Black window for a long time | Wait: without KVM the first start takes several minutes. The console log is in `<image>.qcow2.serial.log`. |
| "Could not set up host forwarding rule" | Port 2222 is in use: `--ssh-port 2233`. |
| The mouse is captured by the window | Press Ctrl+Alt+G (GTK) to release it. |
| You want a clean slate | Delete the `.qcow2` and the files next to it starting with the same name, and extract the artifact again. |

## 9. What was verified, and what was not

The CI job that builds the image boots the exported file with this launcher, as above,
before it is offered for download (KVM; no window, no host sound, OVMF without Secure Boot
keys): the account is created as described, `sudo` accepts the generated password and
refuses a wrong one, root stays locked, the desktop logs in on Wayland at 1920x1080, a
command typed into Konsole runs as the user, networking is connected, an audio device
exists, SELinux is enforcing with no denials, and power-off ends the launcher. First
verified in `build` run 44751864651; results and screenshots: `PROJECT_STATE.md` (GUI v1
track) and `docs/architecture/gui-architecture.md`.

Not tested by the project: Linux Mint itself (the CI runner is Ubuntu 24.04 with QEMU
from Fedora), the GTK and SDL windows, `--gl`, host sound through PulseAudio/PipeWire, and
physical hardware.

## 10. Limits of this image

- **Secure Boot is off in this VM.** The image is sealed (signed UKI, composefs root with
  fs-verity, SELinux enforcing), but the firmware the launcher uses has no AEGIS keys, so
  nothing verifies the boot chain on your computer. The Secure Boot tests run in CI with
  throw-away keys that exist only for one run.
- Software rendering by default (the VM has a virtual GPU without 3D); animations are
  less smooth than on real hardware.
- The image trusts update images signed with the key of the CI run that built it; that
  key is discarded, so this image cannot be updated. Download a newer image instead.
- No disk encryption.

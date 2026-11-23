# AEGIS OS Live ISO in Oracle VirtualBox

`AEGIS-OS-GUI-Live.iso` starts the AEGIS OS graphical desktop (KDE Plasma 6 on Wayland
with the AEGIS look) straight from a virtual CD. Nothing is installed: everything you
do lives in the virtual machine's memory and is gone when it is switched off.

It is a **development** build, not a release. See "Security: what the Live ISO is and
is not" before relying on it for anything.

## 1. Download and check

1. On GitHub: the repository → **Actions** → workflow **live-iso** → a run with a green
   tick that has an artifact named **`aegis-os-gui-live-iso`** (bottom of the run page;
   you must be signed in). GitHub deletes it after 14 days.
2. Download it and extract the ZIP into an empty folder. It contains
   `AEGIS-OS-GUI-Live.iso`, `VIRTUALBOX_GUIDE.md` (this file), `BUILD-INFO.txt` (commit,
   kernel, inputs) and `SHA256SUMS`.
3. In a terminal in that folder (Linux Mint):

   ```bash
   sha256sum -c SHA256SUMS
   ```

   Every line must end in `OK`.

## 2. Create the virtual machine (VirtualBox 7)

In VirtualBox Manager choose **Machine → New**:

| Setting | Value |
|---|---|
| Name | `AEGIS OS Live` |
| ISO Image | `AEGIS-OS-GUI-Live.iso` |
| Type / Subtype / Version | Linux / Fedora / Fedora (64-bit) |
| Skip Unattended Installation | **on** (there is nothing to install) |
| Base Memory | 4096 MB (more is better; 4096 MB is what was tested) |
| Processors | 2 to 4 |
| **Enable EFI (special OSes only)** | **on** (required: the ISO boots with UEFI only) |
| Hard Disk | **Do Not Add a Virtual Hard Disk** |

Finish, then open **Settings** of the new machine and check:

| Page | Setting |
|---|---|
| System → Motherboard | **Enable EFI** on; **Enable Secure Boot** off (see section 6) |
| Display → Screen | Graphics Controller **VMSVGA**, Video Memory **128 MB**, **Enable 3D Acceleration off** |
| Storage | the controller's optical drive holds `AEGIS-OS-GUI-Live.iso` |
| Network → Adapter 1 | Enabled, Attached to **NAT** |
| Audio | enabled (default) |

## 3. Start

Press **Start**. A boot menu appears for five seconds and then starts
**AEGIS OS Live (graphical desktop)** by itself. After about one to two minutes the AEGIS
desktop appears, logged in as the user `aegis`. No password and no commands are needed.

The desktop sets the screen to 1920×1080 at login when the virtual graphics card offers
it. Other sizes: System Settings → Display & Monitor. Make the VirtualBox window large
enough (View → Virtual Screen 1 → or full screen with Host+F).

## 4. What to try

- The floating dock at the bottom: launcher (AEGIS mark), Files (Dolphin), Terminal
  (Konsole), System Settings, the **AEGIS Security** widget, clock. **Ctrl+Alt+T** opens
  a terminal.
- The AEGIS Security widget shows the real state of this live session: SELinux
  enforcing, firewall active, kernel lockdown, and, honestly, that the root is not sealed
  and Secure Boot is off (both marked as warnings).
- In Konsole: `getenforce` (Enforcing), `cat /etc/os-release`.

## 5. Administrator access (development only)

The desktop account `aegis` is **unprivileged**: it has no password, is not an
administrator, and `sudo` does not work for it.

For administration, each boot creates a **new random password for `root`**. It is not on
the ISO, the desktop account cannot read it, and it disappears when the machine is
switched off. It is shown only on the text console:

1. Press **Host+F3** (VirtualBox's Host key is the right Ctrl key by default; this sends
   Ctrl+Alt+F3 to the machine). A text login screen shows the line
   `user: root    password: xxxx-xxxx-xxxx-xxxx`.
2. Return to the desktop with **Host+F1** (or Host+F2, whichever shows the desktop).
3. In Konsole run `su -` and type that password.

Whoever can use the virtual machine's console can read it; that is no more than they
already control (the boot menu has no password either). Logging in as root over the
network with a password is refused.

## 6. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "No bootable medium found" or the EFI shell appears | EFI is off, or the ISO is not in the optical drive. Settings → System → Enable EFI; Settings → Storage. |
| Secure Boot violation / boot refused | Turn **Enable Secure Boot** off (Settings → System). The ISO's boot loader is Fedora's signed shim and GRUB, but booting under Secure Boot was not tested. |
| Black screen or a garbled desktop | In the boot menu (first five seconds, use the arrow keys) choose **AEGIS OS Live (basic graphics…)**. It uses the firmware's framebuffer (fixed size, slower). Also check that 3D acceleration is off. |
| Very slow desktop | Give the machine 4 CPUs and more memory; make sure VirtualBox uses hardware virtualization (on Linux Mint, KVM must not hold it: VirtualBox 7.0/7.1 cannot run while another hypervisor such as a running QEMU/KVM machine uses VT-x). |
| The screen stays at a small size | System Settings → Display & Monitor → choose 1920×1080. VirtualBox's automatic resizing needs the VirtualBox Guest Additions, which the ISO does not contain. |
| No network | Settings → Network → Adapter 1 → NAT. |
| Mouse is captured | Press the Host key (right Ctrl). |

## 7. Security: what the Live ISO is and is not

The Live ISO reuses the AEGIS OS graphical root file system (the same one that the
sealed `aegis-gui` image is made of), but it boots differently. It does **not** have the
protections of an installed, sealed AEGIS OS image:

| Protection | Installed sealed image (QCOW2 / disk) | Live ISO |
|---|---|---|
| Secure Boot with AEGIS keys, signed UKI | yes (tested in CI) | **no**: Fedora's signed shim and GRUB load the Fedora kernel; Secure Boot not tested |
| Sealed root (composefs + fs-verity digest in the signed command line) | yes | **no**: a read-only SquashFS plus a writable overlay in RAM; nothing verifies the SquashFS's content at boot |
| Kernel command line check (`aegis-verify-cmdline`) | yes | **no**: removed in the live root, because there is no sealed command line; the boot menu can be edited by whoever has the console |
| Signed updates and rollback | yes | **no**: a live session cannot be updated |
| SELinux enforcing, AEGIS policy | yes | **yes** (files labelled at build time; tested: no denials) |
| Kernel lockdown (integrity) and the other AEGIS kernel arguments | yes | **yes** (the same arguments in the boot menu) |
| Firewall (AEGIS zone), hardening sysctls | yes | **yes** (same root file system) |
| Persistent changes | yes | **no**: everything is lost at power-off |

It also contains the development SSH server (public-key login only, no keys present).

## 8. What was verified, and what was not

The `live-iso` workflow builds the ISO and, before offering it for download:

- checks the ISO: checksums, the volume label, the UEFI El Torito boot image and the boot
  menu (default entry, five-second timeout, AEGIS kernel arguments, nothing weakened);
- boots it in **QEMU/KVM on hardware chosen to resemble VirtualBox's defaults**: i440FX
  chipset, the ISO as a SATA CD-ROM, OVMF UEFI without Secure Boot keys, VMware SVGA II
  display with 128 MB (VirtualBox's VMSVGA is driven by the same guest driver, `vmwgfx`),
  PS/2 keyboard, USB tablet, Intel PRO/1000 MT network card, Intel HD Audio, 4 GiB, 2 CPUs;
- and checks: automatic login of the unprivileged `aegis` account into Plasma on
  Wayland; 1920×1080; typing into Konsole; a right click opening the desktop menu;
  Dolphin and System Settings; the AEGIS Security widget's values; networking; the audio
  device; SELinux enforcing with no denials; no failed services; the per-boot
  administrator password; a clean power-off. Screenshots are in the run's log artifact.

**Not verified: Oracle VirtualBox itself.** The CI runners have no VirtualBox, so the
ISO has not been booted in VirtualBox by the project. VirtualBox's EFI firmware, its
VMSVGA device and its storage controllers are close to, but not the same as, what was
tested. Also not tested: Secure Boot, the "basic graphics" menu entry, 3D acceleration,
host sound output, Linux Mint as the host, and physical hardware.

The run and commit that produced your ISO are in `BUILD-INFO.txt`.

# AEGIS OS Live ISO in Oracle VirtualBox

`AEGIS-OS-GUI-v2-Live.iso` starts the AEGIS OS graphical desktop (KDE Plasma 6 on Wayland
with the AEGIS look) straight from a virtual CD. Nothing is installed: everything you
do lives in the virtual machine's memory and is gone when it is switched off.

It is a **development** build, not a release. See "Security: what the Live ISO is and
is not" before relying on it for anything.

## 1. Download and check

1. On GitHub: the repository → **Actions** → workflow **live-iso** → a run with a green
   tick that has an artifact named **`aegis-os-gui-live-iso`** (bottom of the run page;
   you must be signed in). GitHub deletes it after 14 days.
2. Download it and extract the ZIP into an empty folder. It contains
   `AEGIS-OS-GUI-v2-Live.iso`, `VIRTUALBOX_GUIDE.md` (this file), `BUILD-INFO.txt` (commit,
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
| ISO Image | `AEGIS-OS-GUI-v2-Live.iso` |
| Type / Subtype / Version | Linux / Fedora / Fedora (64-bit) |
| Skip Unattended Installation | **on** (there is nothing to install) |
| Base Memory | 4096 MB for the desktop (tested); **8192 MB to install Google Chrome or other Flatpak applications** (section 5a) |
| Processors | **4** (software rendering spreads over all processors; 2 works) |
| **Enable EFI (special OSes only)** | **on** (required: the ISO boots with UEFI only) |
| Hard Disk | **Do Not Add a Virtual Hard Disk** |

Finish, then open **Settings** of the new machine and check:

| Page | Setting |
|---|---|
| System → Motherboard | **Enable EFI** on; **Enable Secure Boot** off (see section 6) |
| Display → Screen | Graphics Controller **VMSVGA**, Video Memory **128 MB**, **Enable 3D Acceleration off** to start with (see section 3a) |
| Storage | the controller's optical drive holds `AEGIS-OS-GUI-v2-Live.iso` |
| Network → Adapter 1 | Enabled, Attached to **NAT** |
| Audio | enabled (default) |

## 3. Start

Press **Start**. A boot menu appears for five seconds and then starts
**AEGIS OS Live (graphical desktop)** by itself. After about one to two minutes the AEGIS
desktop appears, logged in as the user `aegis`. No password and no commands are needed.

Inside VirtualBox the screen size follows the VirtualBox window (section 3a). Under other
hypervisors the desktop starts at 1920×1080 when the virtual graphics card offers it.

## 3a. Full screen, window resizing and graphics speed (GUI v2)

**Full screen and resizing.** The ISO contains Fedora's VirtualBox guest tools
(`virtualbox-guest-additions` 7.2: VBoxService, VBoxClient, VBoxDRMClient), which start
only inside VirtualBox. With the VMSVGA graphics controller they pass the size of the
VirtualBox window to the desktop:

- **Host+F** (right Ctrl+F): full screen. **Host+C**: scaled mode. Resizing the window
  changes the desktop size. View → **Auto-resize Guest Display** must be ticked.
- The dock stays centred at the bottom at every size (tested in QEMU at 1366×768,
  1920×1080 and the largest mode QEMU's card offers).
- If the size does not follow the window: System Settings → Display & Monitor lists the
  sizes the card offers (1366×768, 1920×1080, 2560×1440 and more).

The automatic resizing itself has **not** been tested by the project: QEMU cannot
simulate a VirtualBox window being resized. Please report whether it works.

**Why the desktop was slow, and the rendering profiles.** Without 3D acceleration the
VM has no graphics processor: every frame of the desktop is drawn by the CPU
(Mesa's llvmpipe). Measured in QEMU (software rendering, 2 CPUs): drawing the glass blur
behind a popup over moving content made KWin use **about 3 times the CPU** (111–116 % of
one CPU against 37 % without blur) for the same frame rate. GUI v2 therefore picks a
rendering profile automatically at login:

| Profile | Blur | Animations | Chosen automatically when |
|---|---|---|---|
| Full Liquid Glass | strong, with grain | full length, magic-lamp minimise | never (choose it yourself) |
| Balanced Glass | light | 75 % length | the graphics card renders (e.g. 3D acceleration on) |
| Performance Glass | none (more opaque glass) | half length, fewer | software rendering (3D acceleration off) |

Change it with **AEGIS Appearance** (in the dock, or search "Appearance" in the
launcher). In Konsole, `/usr/libexec/aegis/graphics-report --measure` prints the
renderer, the profile and a measured frame rate; please include it in reports.

**3D acceleration.** VirtualBox's 3D acceleration for VMSVGA gives the VM a virtual GPU
(Mesa's `svga` driver), which is much faster than software rendering when it works, but
it depends on the host's graphics driver and is known to be unstable on some hosts.
Start with it off; if you turn it on (Settings → Display → Enable 3D Acceleration), AEGIS
detects the hardware renderer and switches to Balanced Glass. If the desktop shows
glitches or does not start, turn it off again. 3D acceleration has not been tested by
the project (the CI machines have no GPU).

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

## 5a. Installing applications with Flatpak (for example Google Chrome)

Flatpak is included, and **Flathub** is set up as an application source for the live
account. The account is not an administrator, so applications are installed for this
user only (`--user`). In Konsole:

```bash
flatpak install --user flathub com.google.Chrome
```

```bash
flatpak run com.google.Chrome
```

Confirm with `y` when asked. Installed applications also appear in the launcher
(possibly only after the next login, which in a live session means after a restart, so
use `flatpak run` instead). Other examples: `flatpak search firefox`,
`flatpak list --user`.

Important limits of the live session:

- **Nothing you install is kept.** The live system writes into memory; at power-off every
  installed application is gone and has to be installed again at the next start. (Keeping
  changes is a separate, later milestone.)
- **Memory is the storage.** Everything you download and install is kept in memory. The
  live system lets its writable space grow to 75% of the virtual machine's memory (about
  2.9 GB with 4096 MB). Google Chrome with its Flatpak runtime takes **about 2.6 GB** of
  it (measured in CI). With 4096 MB, Chrome installs and starts, but the machine is then
  almost out of memory (about 75 MB left) and may become slow or close applications.
  **Give the machine 8192 MB for Chrome**, more for several applications. `df -h /` in
  Konsole shows the space left, `free -m` the memory.
- Installing needs internet access (NAT is enough). Flathub's applications are built and
  published by their own developers (Chrome by Google, downloaded from Google's servers
  during the installation), not by AEGIS OS or Fedora.

## 6. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "No bootable medium found" or the EFI shell appears | EFI is off, or the ISO is not in the optical drive. Settings → System → Enable EFI; Settings → Storage. |
| Secure Boot violation / boot refused | Turn **Enable Secure Boot** off (Settings → System). The ISO's boot loader is Fedora's signed shim and GRUB, but booting under Secure Boot was not tested. |
| Black screen or a garbled desktop | Turn 3D acceleration off. Otherwise, in the boot menu (first five seconds, use the arrow keys) choose **AEGIS OS Live (basic graphics…)**: the firmware's framebuffer (fixed size, slower). |
| Desktop still feels slow | Give the VM 4 processors; check in AEGIS Appearance that Performance Glass is in use; run `/usr/libexec/aegis/graphics-report --measure`. |
| The size does not follow the window | View → Auto-resize Guest Display; or pick a size in System Settings → Display & Monitor. |
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
  chipset, the ISO as a SATA CD-ROM, OVMF UEFI without Secure Boot keys, PS/2 keyboard,
  USB tablet, Intel PRO/1000 MT network card, Intel HD Audio, 4 GiB, 2 CPUs, and checks:
  automatic login of the unprivileged `aegis` account into Plasma on Wayland; 1920×1080;
  typing into Konsole; a right click opening the desktop menu; Dolphin and System
  Settings; the AEGIS Security widget's values; networking; the audio device; SELinux
  enforcing with no denials; no failed services; the per-boot administrator password; a
  clean power-off. Screenshots are in the run's log artifact.
- with internet access, in a second boot: Flatpak with Flathub as the live account's own
  application source and no system-wide source; `flatpak install --user flathub
  com.google.Chrome` succeeds (into the account's home in the RAM overlay); Chrome starts
  in the desktop; SELinux enforcing with no denials afterwards. Persistence across a
  restart is not tested and not provided.
- **Graphics:** these interactive checks use QEMU's standard VGA, because QEMU's emulation
  of the VMware SVGA II device (the device VirtualBox's VMSVGA presents) does not show what
  a current desktop draws. A second boot with that device checks only that the desktop
  session starts (it did; which kernel driver took the device was not recorded).

- GUI v2, in the same QEMU machine: the renderer is identified (software, llvmpipe) and
  Performance Glass is chosen automatically; each profile switches KWin's blur and the
  animation length as described in section 3a; frame rate and CPU are measured under each
  (see `TEST-REPORT.txt`); the launcher opens and searches; the screen is changed to
  1366×768, 4096×2160 and 1920×1080 and the dock stays centred at the bottom with the
  desktop filling the screen; the VirtualBox guest tools are installed and stay inactive
  outside VirtualBox.

**Not verified: Oracle VirtualBox itself.** The CI runners have no VirtualBox, so the
ISO has not been booted in VirtualBox by the project. VirtualBox's EFI firmware, its
VMSVGA device and its storage controllers are close to, but not the same as, what was
tested. Also not tested: automatic resizing and full screen through the VirtualBox guest
tools, 3D acceleration, what the desktop looks like on VMSVGA, Secure Boot, the "basic graphics" menu entry, 3D acceleration,
host sound output, Linux Mint as the host, and physical hardware.

The run and commit that produced your ISO are in `BUILD-INFO.txt`.

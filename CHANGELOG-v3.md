# AEGIS OS v3 "The Experience Update": development builds

**EXPERIMENTAL development build. Not a release.** Tested automatically in QEMU on
VirtualBox-like hardware; not yet verified in VirtualBox itself. Signed with per-build
development keys; production keys do not exist yet.

## Second development VDI: experimental preview (milestones M9–M13)

New since the first VDI:

- **Signed system updates and rollback** tested on the VDI: an unsigned update and one
  signed by an unknown key are refused; an AEGIS-signed update installs, and your
  account, files, settings, wallpaper and applications are kept; rolling back keeps them
  too. (Within one build; tests across separate builds wait for persistent development
  keys.)
- **Hybrid AEGIS desktop**: translucent top bar with the application in front, its
  menus, search, Quick Settings and clock; floating glass dock; AEGIS login screen; Inter
  typeface; Windows-style snapping and keys; Alt+Tab grid.
- **Welcome to AEGIS**: an interactive tour with the real desktop, keyboard and screen
  reader accessible, reduced motion, resumes where you left off.
- **AEGIS App Center**: search, categories, publisher and permission details, install,
  update and remove for your account only; update notices, never automatic updates.
- **Swap in memory (zram)**, which the desktop lacked.
- Spectacle (screenshots, Meta+Shift+S), Inter and the Orca screen reader (Meta+Alt+S
  turns it on and off) are installed.
- Measured in QEMU (2 CPUs, 4 GiB; not VirtualBox): login screen 7.5 s after a reboot,
  desktop 4.6 s after the password, idle desktop below 0.2 % CPU, about 950 MiB of
  memory in use, applications open in about 3 s.

Fixed:

- Switching to Performance Glass sometimes left KWin's blur running; the glass profile
  now turns each effect on or off in KWin directly (also in the Live ISO's code).
- When the sealed command-line check stops a machine, its reason now always reaches the
  console before the power-off.

- Chrome's first start no longer opens KDE's wallet setup: the password you type at the
  login screen opens your KDE Wallet (Fedora's `pam-kwallet`; no built-in wallet password, closed
  until you log in).

Known issues:

- Not yet tested in VirtualBox itself; every automated test ran in QEMU on
  VirtualBox-like hardware.
- No system updates for this disk: updates between separately built images need the
  persistent development signing keys, which are not set up yet. A newer build is a new
  disk.
- Secure Boot is off in VirtualBox; see section 6 of the guide for what that means.
- The disk is not encrypted.
- Changing your login password does not change the wallet's password; applications then
  ask for the old one.
- KDE applications that use the older KWallet interface (rather than the Secret Service
  that Chrome uses) have not been tested and may ask for the wallet password.
- The App Center's handling of a full disk has not been tested.

## First development VDI (milestone M8, part of M9)

New:

- **Persistent disk for VirtualBox** (`AEGIS-OS-v3-….vdi`, 64 GB, dynamically allocated):
  an installed AEGIS OS. Your account, files, settings, wallpaper and applications are
  kept when you shut the virtual machine down.
- **AEGIS Setup** on the first start: creates your account (name, user name, password,
  administrator choice, time zone). No account or password ships in the image; root
  stays locked; Setup refuses to create a second account.
- **Applications from Flathub for your account only** (no administrator rights needed),
  for example Google Chrome. They stay installed across shutdowns.
- **VirtualBox guest tools** in the installed system (screen size follows the window).
- The GUI v2 desktop (Liquid Glass 2.0, performance profiles, AEGIS Appearance, Security
  dashboard), unchanged.

Security, unchanged from earlier builds: sealed read-only system image (composefs with
fs-verity) whose digest is in the signed startup image; SELinux enforcing; kernel
lockdown; firewall; no SSH server running and no remote login.

Not yet in this build:

- **System updates** (M9): this disk does not receive updates yet. A newer build is a
  new disk; copy your files over.
- Persistent signing keys, verified updates across builds, update rollback tests (M9).
- AEGIS login screen theme, hybrid desktop layout, welcome tour, App Center (M10–M12).
- Disk encryption (later).

See `VIRTUALBOX_V3_GUIDE.md` for setup, backups, recovery and exactly what is and is not
protected with Secure Boot off.

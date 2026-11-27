# AEGIS OS v3 "The Experience Update": development builds

**EXPERIMENTAL development build. Not a release.** Tested automatically in QEMU on
VirtualBox-like hardware; not yet verified in VirtualBox itself. Signed with per-build
development keys; production keys do not exist yet.

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

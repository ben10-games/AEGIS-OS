# AEGIS OS v3 (development): the persistent disk for VirtualBox

`AEGIS-OS-v3-….vdi` is an installed AEGIS OS: everything you do is **kept** on the virtual
disk, including your account, files, settings, wallpaper and applications installed with
Flatpak (such as Google Chrome). Shut down and start again whenever you like.

This is an **experimental development build**, not a release. What was tested, and
where, is in section 8 and in `BUILD-INFO.txt`.

## 1. Download and check

1. GitHub → Actions → workflow **v3** → a run with a green tick that has the artifact
   **`aegis-os-v3-vdi`** (signed-in users only; kept 14 days). Download it (about 3 GB)
   and unzip it into a folder with about 20 GB free. It contains the disk
   (`AEGIS-OS-v3-….vdi`), this guide, `CHANGELOG-v3.md`, `BUILD-INFO.txt`,
   `TEST-REPORT.txt`, `SHA256SUMS` and the public Secure Boot certificates of the build.
2. In a terminal in that folder:

   ```bash
   sha256sum -c SHA256SUMS
   ```

   Every line must end in `OK`.

## 2. Create the virtual machine (VirtualBox 7)

**Machine → New**:

| Setting | Value |
|---|---|
| Name | `AEGIS OS v3` |
| ISO Image | leave empty |
| Type / Version | Linux / Fedora (64-bit) |
| Base Memory | 4096 MB (8192 MB for Chrome and several applications) |
| Processors | 4 |
| Enable EFI | **on** (required) |
| Hard Disk | **Use an Existing Virtual Hard Disk File** → choose `AEGIS-OS-v3-….vdi` |

Then **Settings**:

| Page | Setting |
|---|---|
| System → Motherboard | Enable EFI on; Enable Secure Boot **off** (see section 6) |
| Display → Screen | VMSVGA, 128 MB, 3D acceleration off to start with |
| Network | NAT |

The disk is "dynamically allocated": it starts at about 6–8 GB on your computer and
grows as you use it, up to 64 GB.

## 3. First start: create your account

AEGIS OS ships **without any account or password**. On the first start, **AEGIS Setup**
opens:

1. Enter your full name, a user name (suggested from the name), and a password of at
   least 8 characters, twice.
2. "Administrator" (on by default) lets this account install system updates and change
   system settings with its password.
3. Choose your time zone and press **Create account** (or Enter).

The login screen appears; log in with your password. AEGIS Setup works only while no
account exists: afterwards it is gone and cannot create another account. Whoever first
starts a fresh copy of this disk creates its owner account, as with any newly installed
computer, so do not hand out a copy of your disk after you have set it up.

## 4. Using it

**Welcome to AEGIS** opens after your first login: a short tour you do with the real
desktop (open the launcher and Files, move, snap, maximise and minimise a window, choose
light or dark and a glass style, find an application, see what protects the computer).
Skip it whenever you like; start it again from the launcher (Welcome to AEGIS). It
remembers where you were.

The desktop:

| Where | What |
|---|---|
| Top bar, left | The AEGIS mark (opens the launcher) and the application in front, with its menus |
| Top bar, right | Search (Meta+S), network, sound and notifications, **Quick Settings** (Meta+A), clock and calendar |
| Dock, bottom | The launcher (Meta), your pinned and open applications (Meta+1…9), AEGIS Security |
| Quick Settings | Dark mode, Liquid Glass style, Night Light, Do Not Disturb, screenshot, network, sound, display, lock |

Keys: Meta+E files, Ctrl+Alt+T terminal, Meta+I settings, Meta+Tab overview, Alt+Tab switch
windows, Meta+← / Meta+→ snap to a half, Meta+PgUp maximise, Meta+PgDown minimise, Meta+L
lock, Meta+Shift+S screenshot of an area. Screen size follows the VirtualBox window (View →
Auto-resize Guest Display); Host+F is full screen. In VirtualBox without 3D acceleration,
choose **Performance** glass in Quick Settings for the smoothest desktop.

**Accessibility.** Meta+Alt+S turns the Orca screen reader on and off (give the VM an
audio device to hear it). The tour, the App Center and the desktop can be used with the
keyboard alone; the tour has a **Reduce motion** switch and follows KDE's animation
setting.

**Installing applications: AEGIS App Center** (launcher → AEGIS App Center). Search or
browse, open an application to see who publishes it and what it can access, then
Install. Applications are installed for your account only: no administrator password,
they live in your home folder and stay installed when you shut down. "Verified
publisher" means Flathub confirmed who publishes the app; it does not mean the app has
been checked to be safe, so look at its permissions. The App Center tells you when
updates are available (once a day); it installs them only when you choose Update. The
terminal way also works: `flatpak install --user flathub com.google.Chrome`. Give the VM
8 GB of memory if you use Chrome with several tabs.

## 5. Backups, snapshots and recovery

**Before you rely on it, take a snapshot.** Machine → Take Snapshot (for example
"after setup"). Restoring a snapshot returns the whole disk to that moment. Take one
before every system update as well.

**Snapshots are not backups**: they live in the same folder as the VM. For a backup:

- the whole machine: power off, then File → Export Appliance (an `.ova` file); or
  `VBoxManage clonemedium disk "AEGIS-OS-v3-….vdi" backup.vdi`;
- only your files: copy them out of your home folder (for example to a VirtualBox shared
  folder or a USB stick passed through to the VM).

**System updates are not available in this development build.** A newer build is a new
disk: start it, set it up, and copy your files over (see backups above).

**If the system does not start after an update** (for builds with updates, from M9):
AEGIS keeps the previous version. At the start, press Space to open the boot menu and
choose the previous entry; then run `sudo bootc rollback` and restart. Your files,
settings and applications are not changed by an update or a rollback (they live in
`/var`, which both versions share). For a report, run `bootc status` and
`journalctl -b -1 > previous-boot.txt`.

**If you forget your password**: there is no backdoor and no recovery password. Restore
a snapshot taken before the password was changed, or start the AEGIS Live ISO with this
disk attached as a second disk to copy your files out.

## 6. Security: what this disk protects, and what it does not

**Secure Boot is off in VirtualBox** (VirtualBox does not have this build's keys, and
enrolling them has not been tested yet). With Secure Boot off:

| Still in place | Not independently trustworthy |
|---|---|
| The operating system files form a sealed, read-only image; every file is checked (fs-verity) when read, and a modified file cannot be read. | That the boot loader, kernel and startup image (UKI) that ran are the ones AEGIS built: the firmware does not check their signatures, so someone who can modify the `.vdi` file on your computer could replace them. |
| The running image is the one whose digest is sealed into the boot command line; a changed command line powers the machine off. | Those checks themselves, because a replaced startup image could carry other values. |
| SELinux enforcing, kernel lockdown, firewall, hardened kernel settings; system updates (M9) are accepted only with AEGIS's signature. | Anything protecting the VM from your host computer: whoever controls the host controls the VM. |

AEGIS does not describe this setup as "verified boot". Secure Boot with AEGIS's keys is
tested only in automated QEMU tests.

**Saved passwords (KDE Wallet).** Typing your password at the login screen opens your
KDE Wallet, where applications such as Chrome keep saved passwords; nothing asks you to
set up a wallet. The wallet is encrypted with a key made from your login password, and
there is no built-in wallet password. It stays closed until you log in with your
password, and is open while you are logged in, for every program you run. If you change
your login password, the wallet keeps the old one: applications will ask for the old
password (details: `docs/architecture/v3-kwallet.md`).

**The disk is not encrypted.** Anyone who can read the `.vdi` file (on your computer, a
backup or a copy) can read your files and settings. Keep the file where only you can
read it. Disk encryption is planned for a later milestone.

**No remote login.** The image contains an SSH server for automated tests, but it is
switched off and the firewall blocks it; no SSH key or password is built in.

## 7. Troubleshooting

| Symptom | What to do |
|---|---|
| "No bootable medium" or an EFI shell | Settings → System → Enable EFI; the VDI must be attached as the hard disk. |
| Black screen for a long time on the first start | Wait up to two minutes; give the VM 4 processors. |
| AEGIS Setup says the service is not available | Restart the VM; if it persists, report `journalctl -b -u aegis-provision.socket`. |
| Size does not follow the window | View → Auto-resize Guest Display, or System Settings → Display & Monitor. |

## 8. What was verified, and what was not

The `v3` workflow builds the disk and, before offering it for download, tests in **QEMU**
(not VirtualBox):

- the sealed boot chain of this image under Secure Boot with the build's keys;
- this exact VDI file on VirtualBox-like hardware without Secure Boot keys: AEGIS Setup
  appears on the first start with no account present and the SSH server off; an account
  is created by typing into AEGIS Setup; a second account request is refused; root stays
  locked; the login screen accepts the typed password and the desktop starts; SELinux is
  enforcing with no denials; after a complete power-off and a new start, the account, a
  file, the colour scheme, the glass profile and the wallpaper are still there;
- Google Chrome installed from Flathub into the user's own installation (no system-wide
  source, no administrator rights) starts, and after a complete power-off is still
  installed and starts again, with no SELinux denials.
- the KDE Wallet: opened by the password typed at the login screen (no setup assistant,
  also not when Chrome starts the first time), a saved secret is not in the wallet file in
  plain text, other users cannot read the wallet, nothing runs as the user before the
  login, and after a complete power-off the same password opens the wallet again with
  the secret still in it.
- the desktop: login screen theme, top bar and dock at three screen sizes, Quick
  Settings changing the real settings, each shortcut above starting what it promises,
  snapping and maximising (window positions read from KWin), the screen reader turning
  on and off with Meta+Alt+S;
- Welcome to AEGIS: every exercise completed with real keyboard and mouse input, skip,
  replay, reduced motion, progress kept across a restart and a power-off;
- the App Center: search, publisher and permission details, install with progress,
  update offered but applied only on request, remove, a plain error without the
  internet, an installed application still there after a power-off;
- system updates on this disk within one build: an unsigned update and one signed by an
  unknown key are refused; a signed update installs and keeps the account, files,
  settings and applications; rolling back keeps them too;
- measured: about 7.5 s from a restart to the login screen and 4.6 s from the password
  to the desktop, an idle desktop below 0.2 % CPU, about 950 MB of memory in use (2
  processors, 4 GB; QEMU timings, VirtualBox will differ).

`TEST-REPORT.txt` in the download lists every test of this build and its result.

**Not verified: VirtualBox itself.** These results come from QEMU. The owner's own
VirtualBox test is reported separately in `PROJECT_STATE.md`. **Not verified either:** an
update from one build to a separately built one (it needs persistent development
signing keys, which are not set up yet), and Secure Boot in VirtualBox (see section 6).

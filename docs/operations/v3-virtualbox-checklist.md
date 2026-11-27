# AEGIS OS v3: VirtualBox check (owner)

Development VDI from v3 run 45992321699 (commit `4a69cef`), artifact `aegis-os-v3-vdi`.
Nothing here is marked verified until the owner reports it. Please note for each item:
**OK**, **problem** (what you saw), or **not tried**. Host: Linux Mint, VirtualBox 7.

| # | Check | How |
|---|---|---|
| 1 | Checksums | `sha256sum -c SHA256SUMS`: every line OK |
| 2 | Boots from the VDI | New VM as in `VIRTUALBOX_V3_GUIDE.md` section 2 (EFI on, Secure Boot off, VMSVGA) |
| 3 | AEGIS Setup appears | Within about 2 minutes of the first start |
| 4 | Account creation | Fill in the form, Create account; the login screen follows |
| 5 | Login | Your password at the login screen opens the desktop |
| 6 | Window size | View → Auto-resize Guest Display; resizing the window resizes the desktop |
| 7 | Full screen | Host+F, and back |
| 8 | Chrome | `flatpak install --user flathub com.google.Chrome` in Konsole; Chrome starts from the launcher |
| 9 | Persistence | Change the wallpaper, save a file, keep Chrome; shut down completely (VM closed); start again: all still there |
| 10 | Snapshot | Machine → Take Snapshot; change something; restore; the change is gone |
| 11 | Secure Boot state | AEGIS Security dashboard shows Secure Boot off as a warning |
| 12 | SELinux | `getenforce` prints `Enforcing`; `journalctl -b \| grep -c 'avc:  denied'` prints `0` |
| 13 | Performance | Desktop responsiveness; `/usr/libexec/aegis/graphics-report` output welcome |

Useful for any problem: `journalctl -b > boot.txt`, `bootc status`, a screenshot.
System updates and rollback are not part of this build (M9, needs the signing setup).

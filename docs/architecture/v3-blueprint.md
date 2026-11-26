# AEGIS OS v3 "The Experience Update": implementation blueprint (planning only)

## Context

GUI v2 boots in real Oracle VirtualBox on Linux Mint (owner report): full-screen
resizing works, performance improved, Flatpak and Chrome work. The Live ISO loses every
installed application and setting at power-off, because its writable layer is RAM. v3
must make AEGIS persistent without giving up the sealed, verified OS design, and add a
Windows/macOS hybrid desktop, an interactive first-run experience and a graphical App
Center.

Owner decisions (2026-11-26):

1. **Persistent signing identities.** Development and production keys are kept separate,
   in protected CI release environments. Explicit approval is needed before any
   long-lived secret is created or stored, and before signing trust roots change.
2. **A prebuilt VirtualBox VDI first.** The graphical installer is a separate, later
   milestone (M14) and does not block v3.
3. **What must survive a complete VM shutdown:** Chrome, installed applications, account
   settings, wallpapers, files and onboarding progress.
4. **Sealed OS and updates preserved.** The sealed OS, verified updates and rollback stay;
   signing is tested across separately built images.
5. **Private keys never leave CI secrets.** No private signing key in source control,
   CI artifacts, logs or downloadable VM images.

Owner amendments to the approved plan (2026-11-26):

1. **Priority.** The persistent VDI comes first: M8 and M9 lead. The core requirement is
   that Chrome, apps, accounts, wallpapers, settings and files survive a complete
   shutdown and reboot.
2. **Development signing keys are approved,** created and stored only through a
   protected GitHub Actions environment with restricted publishing permissions.
   **Production keys and production trust-root changes need separate approval.**
   Private keys never appear in source control, images, logs or artifacts.
3. **Secure Boot honesty (§8a).** If Secure Boot stays off in VirtualBox, the docs say
   which integrity guarantees remain and which cannot be independently trusted. No
   claim of a fully verified boot chain until its trust anchor and boot path have been
   tested.
4. **Recovery and backups (§11a).** VirtualBox snapshot and backup procedure, recovery
   guidance, update-failure handling; user data protected during upgrade and rollback.
5. **Premium hybrid UX,** an original Windows-productivity and macOS-elegance
   combination, not default KDE panels; screenshots and visual validation at several
   resolutions; glass kept performance-aware.
6. **Cinematic, genuinely interactive onboarding,** with validated real input, scene
   transitions, drag-and-drop or window exercises, keyboard accessibility and
   persistent completion state. Not a slideshow.
7. **App Center:** user-scoped, persistent installs; publisher verification is clearly
   distinguished from any claim that an app is safe.
8. **Keep everything that exists:** all existing security tests and GUI v2 functions; the
   Linux Mint host and physical disks are never modified.
9. **M14 installer stays separate** and never delays the VDI.
10. **Milestone by milestone:** real integration tests, actual results reported, QEMU
    results kept separate from VirtualBox validation.

Starting point: `claude/aegis-os-gui-v2` @ `0821eb8`. The GUI v2 release (artifact
`aegis-os-gui-v2-live-iso`, run 45611819540) stays untouched. No code is written until
this plan is approved.

---

## 1. Repository audit (verified in the code, not assumed)

| Area | What exists | File(s) | Reuse in v3 |
|---|---|---|---|
| Base | Digest-pinned `fedora-bootc` 45, mirrored to GHCR; RPM lock (P1-15) with steps base/dev/dev-policy/gui/live/live-apps/builder; builds `--network=none` | `image/base.lock`, `image/packages/rpms.{in,lock}.yaml`, `scripts/rpmlock.py`, `scripts/bump-inputs`, `.github/workflows/update-inputs.yml` | As is. New steps for v3 packages. |
| Images | base → dev → gui root filesystems; sealing (`Containerfile.seal`: composefs digest in the signed UKI cmdline); throw-away Secure Boot keys (`scripts/dev-keys`) and image-signing key (`scripts/signing-keys`) per build (ADR-0007) | `image/Containerfile*`, `scripts/build-image`, `scripts/storage-digest`, `image/build/seal-uki` | Sealing as is; key source becomes the persistent identity (M9). |
| Disk | `bootc install to-disk --via-loopback --generic-image --filesystem btrfs` into a regular image file; refuses block devices; fixes `default_t` labels (BUG-1). Layout: GPT, BIOS-boot partition, 512 MiB ESP, btrfs root (composefs backend; deployment `/etc` and shared `/var` under `/state` on the root partition) | `scripts/build-disk`, `scripts/fix-install-labels` | **Core of the v3 VDI.** |
| Export | `scripts/export-qcow2` (dev, `--gui`), Linux launcher with SMBIOS-credential account creation, Windows launcher | `scripts/export-qcow2`, `local-vm/*` | Extend with `--vdi`. SMBIOS credentials are QEMU-only, so they are not usable in VirtualBox. |
| Security | SELinux enforcing plus an AEGIS policy module; sealed cmdline check (`aegis-verify-cmdline`, powers off on mismatch); lockdown=integrity and hardening kargs; sysctl hardening; firewalld zone `aegis`; root locked; signed-update policy `policy/containers/policy.json` (sigstoreSigned, key at `/usr/share/aegis/keys/aegis-os-signing.pub`, everything else rejected) | `image/rootfs/**`, `policy/**` | Unchanged. |
| Updates | V-13/V-14/V-15/V-09: update from a test registry (signed v2 accepted, unsigned or untrusted refused, rollback) under Secure Boot, within **one** build | `tests/vm/test_update.py`, `tests/vm/harness/registry.py` | Extend to two separately built images (M9). |
| Tests | Static rules (147); M1–M5 VM suite; reproducibility R-01/R-02; GUI under Secure Boot (`test_gui.py`); local-image tests; Live ISO offline (24) and network (5) suites; frame meter and CPU measurements | `tests/**`, `.github/workflows/{build,live-iso,lint}.yml` | All kept; v3 adds a VDI suite. |
| GUI v2 | Plasma 6.8 Wayland (Wayland only); AEGIS Glass theme generator; profiles (`glass-profile`); AEGIS Appearance, Security Dashboard, Frame Meter plasmoids; Kickoff (the Application Dashboard is absent in this build); dock with `dodgewindows`; Baloo off | `image/rootfs-gui/**`, `scripts/make_plasma_theme.py` | Base of M10. |
| VirtualBox | `virtualbox-guest-additions` 7.2.22 in the **live** root only (`live-apps`); units conditioned on `oracle` | `image/Containerfile.live` | Move into the installed image (M8). |
| Flatpak | Live root only: flatpak, flatpak-selinux, fedora-flathub-remote; per-user Flathub remote unit; no system remote; `flatpak-add-fedora-repos` masked | `image/Containerfile.live`, `image/rootfs-live/**` | Move into the installed image (M9). |
| Live storage | SquashFS plus a RAM overlay (75 % of memory); nothing persists | `scripts/build-live-iso`, `assemble-live-iso` | Unchanged; the ISO stays the "try it" medium. |
| Accounts | Base: no users, root locked. QCOW2: user from SMBIOS credentials. Live: sysusers `aegis` with autologin and a per-boot root password on the console | launcher, `image/rootfs-live/**` | **New first-boot provisioning needed (M8).** |
| Available packages | In the lock: accountsservice, kf6-kirigami-addons, appstream-qt, kio-extras; zram-generator in base | lock | Not present: plasma-discover, spectacle, compilers or Qt `-devel` packages. |
| CI limits | GitHub `ubuntu-24.04`: KVM, no GPU, no VirtualBox; ~80 GB free disk; artifacts kept 14 days; this session reads job logs through a ~700 kB tail (screenshots must stay small) | — | Shapes the test design. |

New implementation is needed for: VDI export, first-boot account setup, persistent
signing, the welcome app, the App Center, a compiled-apps build stage, and the hybrid UX
pieces that Plasma lacks.

## 2. Persistence architecture: A, the installed sealed bootc disk, delivered as a VDI

| Criterion | A: installed sealed disk (VDI) | B: Live ISO plus data disk | C: installer onto an empty disk |
|---|---|---|---|
| Security | Sealed composefs root, signed UKI, cmdline check, signed updates | Unverified SquashFS root; editable boot menu | Same as A once installed; the installer itself can wipe disks |
| Complexity | Low: `build-disk` exists | Medium: overlay and home mount logic | High: UI, disk selection, safety checks |
| Testing | Boot the same raw disk in QEMU (existing harness) | Two-disk live boots | Install flow plus installed system |
| SELinux | Labels set by `bootc install` (proven) | Persistent overlay labelling is tricky | As A |
| Updates/rollback | bootc, already tested (V-13/14) | None | As A |
| Persistence | Everything under `/var` and `/etc` | `/home` only; apps partly | As A |
| Disk | 64 GiB dynamic VDI, ~6 GB used at start | ISO plus a data VDI | ISO plus an empty VDI |
| Accounts | First-boot setup (M8) | Live user only | Installer step |
| VirtualBox boot | UEFI, systemd-boot plus UKI; Secure Boot off unless keys enrolled | Proven (GUI v2) | As A |
| Reproducibility | R-01/R-02 apply to the image | Weaker | As A |
| Recovery | bootc rollback; replace the VDI | Data disk survives | Reinstall |

**Decision: A** (owner choice: VDI first, installer later as M14). It reuses the sealed
design unchanged, never touches the user's real disks (the disk is a file built in CI),
and is tested by booting exactly the bytes that are published.

### Storage layout of `AEGIS-OS-v3.vdi` (64 GiB virtual, dynamically allocated)

```
GPT
├─ p1  BIOS boot      1 MiB    (created by bootc; unused under UEFI)
├─ p2  ESP (vfat)     512 MiB  systemd-boot (signed) + UKI(s) per deployment, cmdline holds composefs digest
└─ p3  root (btrfs)   rest     ──┬─ composefs object store (read-only OS images, fs-verity)
                                 └─ /state/os/<os>/
                                      ├─ deploy/<id>/etc   per-deployment /etc (3-way merged on update)
                                      └─ var/              SHARED across deployments and rollbacks
                                           ├─ home/<user>/            files, ~/.config (settings, wallpaper choice),
                                           │                          ~/.local/share/flatpak (user Flatpak apps incl. Chrome),
                                           │                          ~/.local/share/wallpapers, ~/.local/state/aegis (onboarding)
                                           ├─ lib/flatpak/            system installation (unused by default)
                                           ├─ lib/aegis/provisioned   first-boot marker
                                           └─ log, cache, …
```

How each item survives a shutdown:

| Item | Where it lives | Survives reboot | Survives update or rollback |
|---|---|---|---|
| Files, settings, wallpapers, onboarding state | `/var/home/<user>` | yes | yes (`/var` is shared) |
| Chrome and Flatpak apps | `~/.local/share/flatpak` (user installation) | yes | yes |
| Accounts | `/etc/passwd`, `shadow`, `group`, `gshadow` | yes | carried by bootc's `/etc` merge; **to be proven in M9** |
| Machine ID, NetworkManager connections | `/etc` | yes | merged |
| OS itself | composefs objects | read-only | replaced or rolled back as a whole |

Lifecycle:

1. CI builds the sealed gui image.
2. `build-disk` writes it to a 64 GiB sparse raw image.
3. `qemu-img convert -O vdi` makes the VDI (a zip-compressed artifact).
4. The user creates a VM with "Use an existing virtual hard disk".
5. First boot: tmpfiles populates `/var`, then first-boot setup creates the account.
6. Normal use.
7. Updates: `bootc upgrade` fetches the signed image from GHCR, stages it, and it
   becomes active at the next reboot; `bootc rollback` returns to the previous one.

## 3. Authentication and first-boot design (M8)

- The image ships no account and no password; root stays locked. In VirtualBox there are
  no SMBIOS credentials to pass a user in.
- **First boot:** `aegis-firstboot.target` runs while `/var/lib/aegis/provisioned` is
  absent. SDDM starts a dedicated kiosk session as the system user `aegis-setup` (no
  shell, no password, not in wheel): `kwin_wayland` runs only the **AEGIS Setup** app
  (QML). Its steps are language and keyboard, time zone, network (optional), the account
  (full name, username, password entered twice, strength meter), and the
  administrator choice (default: yes, in `wheel`).
- **Privileged helper `aegis-provision`:** a D-Bus system service (or a systemd
  socket-activated varlink service). It accepts exactly one CreateFirstUser request,
  and only while unprovisioned. Polkit allows only the `aegis-setup` user.
  - It validates the username against `^[a-z_][a-z0-9_-]{0,31}$` and rejects reserved
    names.
  - It hashes the password with yescrypt (`chpasswd`), creates the user and home, and
    writes the `provisioned` marker.
  - It then disables the setup session, removes `aegis-setup` from SDDM autologin and
    reboots into SDDM's normal greeter.
  - Afterwards it refuses every request.
- **No fixed credentials anywhere.** The trust model is that whoever first starts the
  VM's console owns it, as with any fresh OS install; this is documented.
- **Before implementing,** check whether Fedora 45 packages KDE's `plasma-setup`. If it
  does and fits these rules (no fixed credentials, works offline), configure it instead
  of AEGIS Setup.
- **Login after setup:** SDDM with the AEGIS theme, password login, no autologin. The
  lock screen works because the user has a password, which removes the live-only
  KWallet and screen-lock workarounds.
- **CI:** boot the disk without user credentials (only the test SSH key), drive AEGIS
  Setup with QMP keystrokes, reboot, log in through SDDM by typing the password, then
  check `id`, `wheel` membership, `sudo` and root still locked. A second request to the
  helper must be refused.

## 4. Desktop UX specification (M10): original AEGIS hybrid

Built from supported Plasma 6.8 parts plus a few AEGIS plasmoids; no replacement of
KWin or plasmashell.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ ◆ AEGIS   App name ▾                       ⌕ Search   ◐ Quick  🔔  Tue 14:02   │ ← top glass bar (28 px)
│                                                                               │
│      ┌──────────────────────────┐ ┌──────────────────────────┐                │
│      │ Dolphin (snapped left)   │ │ Chrome (snapped right)   │                │
│      └──────────────────────────┘ └──────────────────────────┘                │
│                                                                               │
│          ╭──────────────────────────────────────────────────────╮             │
│          │ ◆ │ 📁 🖥 ⚙ 🛍 ◉Chrome •  │  Downloads ▣  Trash 🗑 │             │ ← floating glass dock
│          ╰──────────────────────────────────────────────────────╯             │
└───────────────────────────────────────────────────────────────────────────────┘
```

| Component | Windows-inspired function | macOS-inspired quality | Implementation |
|---|---|---|---|
| Launcher | Start menu with search, pinned and all apps, power | Glass popup, smooth open | Kickoff (grid, AEGIS theme), Meta opens it |
| Top bar | System tray, clock, notifications | Translucent menu-bar strip | Plasma panel (top, 28 px): `org.kde.plasma.appmenu` (global menu where apps support it), KRunner button, AEGIS Quick Settings, notifications, clock |
| Dock | Taskbar: running apps, previews, Meta+1…9 | Floating glass, magnify-free hover lift, dots | Existing floating panel plus icontasks (preview tooltips on), separator, folder and trash applets |
| Quick Settings | Action Center | Control Center tiles | New plasmoid `org.aegisos.quicksettings`: Wi-Fi, Bluetooth, volume, brightness, Dark/Light, Glass profile, Do Not Disturb, Night Light; uses Plasma's existing D-Bus or DataSources, no privileges |
| Snapping | Snap to halves and quarters, snap layouts | Smooth tile animation | KWin quick tiling (Meta+arrows, drag to edge) plus Plasma 6 custom tiling (Meta+T) with AEGIS default layouts |
| Task switching | Alt+Tab grid, Task View | Fluid overview | KWin "Thumbnail Grid" switcher, Overview effect (Meta+Tab) |
| File manager | Explorer layout | Clean sidebar | Dolphin: places panel, breadcrumb, details or icons, AEGIS Places (Home, Downloads, Documents, Pictures, Apps) |
| Search | Windows Search | Spotlight look | KRunner centred (Meta+S, Alt+Space), with apps, files and settings plugins |
| Appearance | Light/Dark | Automatic switch | AEGIS Dark/Light plus an optional time-based switch (KNightTime / Plasma 6 day-night if present, else an AEGIS timer) |
| Windows | Familiar buttons on the right | Rounded, soft shadows | Breeze decoration; spectacle for screenshots (new package) |

Shortcuts (set in `kglobalshortcutsrc` defaults):

| Keys | Action |
|---|---|
| Meta | Launcher |
| Meta+S / Alt+Space | Search |
| Meta+E | Files |
| Meta+I | Settings |
| Meta+A | Quick Settings |
| Meta+N | Notifications |
| Meta+←/→/↑/↓ | Snap, maximise, restore |
| Meta+T | Tile layouts |
| Alt+Tab | Switch windows |
| Meta+Tab | Overview |
| Meta+D | Desktop |
| Meta+L | Lock |
| Meta+V | Clipboard |
| Meta+Shift+S | Screenshot region |
| Meta+1…9 | Dock apps |
| Ctrl+Alt+T | Terminal |
| Meta+Ctrl+←/→ | Virtual desktops |

Typography: Noto Sans (installed), 10 pt UI and 9 pt small; Inter only if the owner
accepts a new font package.

## 5. Interactive onboarding architecture (M11): "Welcome to AEGIS"

- **Technology:** a Qt Quick/QML application in C++ (Kirigami where useful), built in a
  new locked compile stage (§12 decision). It runs as the logged-in user and needs no
  privileges.
- **Structure:** a `SceneController` C++ state machine (QStateMachine-like enum plus
  QML `StackView`). Each scene is a QML component with `required` hooks: `enter()`,
  `exit()`, `completed` signal, `skippable`, `reducedMotionVariant`.

| Scene | Interaction (reacts to real input) | Real or simulated |
|---|---|---|
| 1. Introduction | Animated AEGIS mark plus glass panes (about 6 s, any key or click continues); first-run only | Simulated (in-app) |
| 2. Dock and launcher | "Open the launcher": detects the real Kickoff open (KWin script reports a plasmashell popup) or Meta press; "Open Files from the dock": detects a Dolphin window | **Real desktop** (KWin script → D-Bus) |
| 3. Windows | Drag, resize, snap left, maximise a real Dolphin window; each step is checked from KWin window geometry events | **Real windows** (KWin script `windowAdded`, `frameGeometryChanged`, `quickTileModeChanged` → `callDBus`) |
| 4. Personalisation | Light/Dark, accent and Glass profile previews applied live (`glass-profile`, `plasma-apply-colorscheme`) with undo | Real settings, reversible |
| 5. Installing apps | Search in an embedded App Center view; optional real install of a small app (needs network) | Real if online; offline shows a simulated catalogue |
| 6. Security and privacy | Interactive cards: Security Dashboard values, SELinux, sealed OS, updates, Flatpak permissions | Real read-only data |
| 7. Completion | Summary, "Replay from Settings", enter desktop | — |

- **Animations:** Qt Quick `Behavior`/`ParallelAnimation`, easing `OutCubic` (enter),
  `InOutQuad` (transitions), 200–400 ms. All durations are scaled by the user's
  `AnimationDurationFactor`, and are 0 when reduced motion is on (KDE setting or the
  app's own toggle).
- **Performance fallback:** on a software renderer, or with the Performance Glass
  profile, there are no layer blurs or particle effects, opaque glass, and at most 30 s
  of total animation.
- **Errors:** every real-desktop step has a timeout hint ("Need help?"), a "Show me"
  demo, and "Skip step". A KWin-script load failure falls back to the simulated scene and
  is logged. Offline: scene 5 uses the bundled sample catalogue.
- **State:** `~/.local/state/aegis/welcome.json` holds version, completed scenes and a
  done flag, so a reboot mid-tour resumes. Autostart `aegis-welcome.desktop` (phase 2)
  runs only if not done. "Welcome to AEGIS" in the launcher and Settings replays it.
  Skipping all writes done with `skipped: true`.
- **Accessibility:** full keyboard path (Tab, Enter, Esc), `Accessible.name` on
  everything, large-text scaling, high-contrast-safe colours, captions for any motion
  meaning. A screen reader (Orca) is not installed; that is an open question.

## 6. App Center architecture (M12): "AEGIS App Center"

**Evaluation.** Plasma Discover with its Flatpak backend is mature, but it is not in the
lock. Its default target is the system installation, which needs polkit administrator
rights, and its UX and permission view are generic. **Decision: a custom Kirigami app**
with a thin C++ backend.

- **Catalogue:** AppStreamQt (`appstream-qt`, in the lock) reads Flathub's AppStream
  data from the user installation (`~/.local/share/flatpak/appstream/flathub/...`),
  refreshed with `flatpak_installation_update_appstream_full_sync`. It provides search,
  categories, screenshots, descriptions, licence, developer, and Flathub's
  `flathub::verification::verified` custom key for the "Verified" badge.
- **Operations:** libflatpak (`flatpak-devel` at build time, `flatpak-libs` at run time)
  on `flatpak_installation_new_user()` **only**:
  - `FlatpakTransaction` handles install, uninstall and update, with
    `new-operation`/`progress`/`operation-error` signals mapped to a QML progress model.
  - Signature verification is libflatpak's (GPG from the Flathub remote definition in
    Fedora's `fedora-flathub-remote`). Unverified remotes are refused; adding remotes is
    not offered.
- **Permissions:** shown before install from the app's metadata (`flatpak_remote_ref_get_metadata` →
  `[Context]` keys), in plain language with risk levels: "full file system access",
  "devices", "network", "X11 fallback". After install, a link opens Plasma's Flatpak
  permissions KCM, if available.
- **Verification wording (amendment 7):**
  - The badge says **"Verified publisher"**, with the explanation: "Flathub has
    confirmed that this app is published by its developer. This does not mean AEGIS or
    Flathub has checked that the app is safe; its permissions below show what it can
    access."
  - Unverified apps say "Publisher not verified".
  - No wording anywhere calls an app "safe" or "secure".
  - A static test scans the App Center's strings for such claims.
- **Updates:** checked in the background at login and daily
  (`flatpak_installation_list_installed_refs_for_update`); badges in the App Center and
  an optional notification. Updates are never applied without user action, or through
  a user timer if the owner prefers.
- **Errors:** errors map to messages such as "No internet connection", "Not enough disk
  space (needs X, Y free)", "Signature check failed: not installed" and "Flathub is
  unavailable", each with a Retry action.
- **Privileges:** none. Installs stay in the user's home on the persistent disk.

## 7. Performance strategy (M13 plus continuous)

- **Keep** the GUI v2 profiles, Frame Meter, `graphics-report` and the CPU-share method.
  Add the same measurements on the VDI (boot to SDDM, boot to desktop, idle, app
  launches) to the report.
- **Memory:**
  - The persistent disk removes the RAM overlay (live Chrome needed 2.6 GB of RAM).
  - Verify the zram swap from `zram-generator` (in base) with `swapon` and measure.
  - Measure plasmashell and KWin RSS against the GUI v2 numbers (903–1354 MiB used).
- **Storage I/O:**
  - Measure btrfs `compress=zstd:1` for `/var` (fewer bytes written to the VDI, cheap
    CPU) before adopting it.
  - Flatpak user installs share OSTree hardlinks.
  - Optionally `fstrim.timer` so dynamic VDIs can shrink.
- **Boot:**
  - `systemd-analyze` and `blame` on the VDI.
  - Disable units that are unneeded in the GUI image (candidates from the inventory)
    only with measurements and rationale (service-baseline rules).
- **Rendering:** unchanged GUI v2 logic, plus a measured test of Qt Quick's software
  scene graph for plasmashell under llvmpipe (one A/B in CI) before deciding.
- **Budgets** (QEMU, 2 CPUs, 4 GiB; VirtualBox numbers from `graphics-report` by the
  owner):
  - idle KWin CPU < 3 %;
  - frame meter ≥ 55 fps;
  - boot to SDDM ≤ GUI v2 + 10 %;
  - memory after login ≤ 1.5 GB.

## 8. Security threat considerations

| Threat | Mitigation |
|---|---|
| Leaked persistent signing key | Separate **dev** and **prod** keys. Each is stored only as a secret of a protected GitHub environment (`aegis-dev-signing`, `aegis-prod-signing`), usable only by the publish job on named branches, with required reviewer for prod. Keys are never written to the workspace beyond a `0600` tmpfs file deleted in `always()`; gitleaks and static tests check that no PEM is ever in the repo or artifacts. Rotation procedure documented in a new ADR (supersedes ADR-0007 for published channels). Private Secure Boot db keys likewise. |
| Malicious update | bootc pulls only from `ghcr.io/ben10-games/aegis-os`; `policy.json` sigstoreSigned with the channel's public key baked into the image; everything else rejected (existing V-09/V-15 tests extended across builds). |
| Wrong trust root shipped | The image contains only public keys; a static test compares them with fingerprints recorded in the repo (no key material). Changing them needs owner approval (requirement 1). |
| First-boot hijack | Setup runs only on the local console, before any user exists; the helper refuses once provisioned; no network listener; SSH (dev variant only) accepts keys only. |
| Privilege escalation via helpers | `aegis-provision` has a minimal D-Bus API, polkit restricted to `aegis-setup`, SELinux confined domain (new policy module), runs once. App Center and welcome app run unprivileged. |
| Flatpak apps | Flathub signatures enforced by libflatpak; permissions shown before install; no system-wide installs; SELinux enforcing (flatpak-selinux). |
| Secure Boot in VirtualBox | See §8a: what remains and what cannot be trusted without it. Enrolling the **public** dev PK/KEK/db certificates with VirtualBox `modifynvram` is a spike, claimed only after the owner tests it in real VirtualBox. |
| Lost disk or theft | No disk encryption in v3 by default. TPM2-bound LUKS (VirtualBox 7 offers a vTPM; CI has swtpm) is an open question, because recovery secrets must never be committed. |

## 8a. Secure Boot honesty (amendment 3)

`VIRTUALBOX_V3_GUIDE.md` and the dashboard state this plainly. With Secure Boot **off**
(the VirtualBox default, and the state until enrollment is tested):

| Still holds | Cannot be independently trusted |
|---|---|
| The OS files are a composefs image with fs-verity: a changed file fails to read (V-07). | That the UKI, kernel and initramfs that started are the ones AEGIS built: the firmware does not check the signature, so anyone who can write the ESP (the VDI file) can replace them. |
| The running root's digest is the one in the UKI's command line, and `aegis-verify-cmdline` powers off on a changed command line. | Those checks themselves, because a replaced UKI could carry a different digest and drop the check. |
| SELinux enforcing, lockdown=integrity, hardening, signed **updates** (signature checked by the running system before staging). | Protection against someone with write access to the VDI file on the host (the hypervisor host is outside the trust boundary in this configuration). |

- **"Verified boot" wording:** neither the dashboard nor the docs say "verified boot"
  while `secureboot=disabled`. The dashboard already reports Secure Boot as a warning.
- **A future "verified boot chain" claim needs all of:**
  - the public dev certificates enrolled in VirtualBox's NVRAM;
  - Secure Boot on;
  - a boot of the VDI with `bootctl status` showing Secure Boot enabled and the AEGIS
    db key in use;
  - a tampered-UKI refusal, all in real VirtualBox (owner-run check-list).
- **CI:** CI keeps testing the full chain in QEMU with enrolled keys (existing M3
  tests), labelled as QEMU.

## 9. CI and testing strategy

| Suite | Where | What |
|---|---|---|
| Static (`lint.yml`) | every push | Rules for new files, theme regeneration, no private keys, public-key fingerprints, QML lint (`qmllint` in the builder), unit tests of pure logic (state machine, permission mapping) in Python or QtTest |
| `build.yml` (unchanged) | every push | M1–M5, R-01/R-02, GUI under Secure Boot, so existing guarantees stay visible |
| **New `vdi.yml`** | push to v3 branches, plus `[publish-vdi]` | Build gui image, then `build-disk`, then raw → VDI. VDI test boots the raw disk in QEMU (2 CPUs, 4 GiB, VirtualBox-like hardware from `VmConfig.virtualbox_like`, a new `writable_disk` mode for SATA/AHCI): first-boot setup via QMP, reboot, login, desktop, install Chrome (network suite), **power off, boot again, check Chrome, settings, wallpaper, files and onboarding state persisted**, `bootc status` |
| **Cross-build update test** | `vdi.yml`, dev key | Image N (signed with the persistent dev key in run A) is upgraded to image N+1 from a **later run B**: accepted; an image signed with a throw-away key: refused; rollback restores N with user data intact |
| Live ISO (`live-iso.yml`) | unchanged | GUI v2 ISO keeps building, but no new publish of v2 |

Screenshots in logs: at most 3 small images per job (log-tail limit); all images in the
uploaded artifact. Every report states "QEMU, not VirtualBox".

## 10. Milestones

Work happens on `claude/aegis-os-v3` (from `claude/aegis-os-gui-v2`). Any parallel work
goes on per-milestone branches; merging between branches needs owner approval each
time.

### M8: Persistent VDI and secure account provisioning

- **Objectives:** VDI export; VirtualBox guest tools in the installed gui image;
  first-boot setup and helper.
- **Likely changes:**
  - `scripts/export-qcow2` (or a new `scripts/export-vdi`);
  - `image/packages/rpms.in.yaml` (gui: `virtualbox-guest-additions`; new
    `apps-build` step with cmake, gcc-c++, extra-cmake-modules, qt6 and kf6 `-devel`);
  - new `apps/` (CMake: aegis-setup) and a build stage in `image/Containerfile.gui`;
  - `image/rootfs-gui/` (SDDM config, setup session, `aegis-firstboot.target`, polkit
    rule);
  - `policy/selinux/aegis_provision.{te,fc}`;
  - `tests/vm/test_vdi_setup.py`;
  - `.github/workflows/vdi.yml`;
  - `VIRTUALBOX_V3_GUIDE.md`.
- **Decisions:** plasma-setup vs AEGIS Setup (spike first); VDI artifact compression
  (zip vs `.vdi.zst`).
- **Acceptance:**
  - the VDI boots in QEMU on VirtualBox-like hardware;
  - setup creates exactly one user; the helper refuses a second request;
  - root stays locked; SELinux enforcing with zero denials;
  - sealed cmdline, verify-cmdline and composefs still active (existing M3 tests run on
    the VDI image).
- **Security checks:** polkit rule tests, a static test that there is no fixed password
  or hash, AVC check.
- **Risks:**
  - `kwin_wayland` kiosk session under SDDM may be fiddly. Fallback: SDDM greeter-mode
    setup.
  - The compile stage adds lock churn.
- **Rollback:** the branch stays unpublished; GUI v2 untouched.
- **Done:** the `aegis-os-v3-vdi` dev artifact passes all of the above.

### M9: Persistent apps, settings, signed updates, reboot validation

- **Precondition (amendment 2):** dev keys are **approved**. They are created by a
  dedicated, manually started workflow job that runs in the protected environment
  `aegis-dev-signing` (restricted to the v3 branch, publishing job only) and writes them
  straight into that environment's secrets. They are never printed, uploaded or written
  outside a `0600` tmpfs. If the session's GitHub permissions cannot create environment
  secrets, the owner is given the exact steps. **No prod keys** and no prod trust-root
  change without separate approval.
- **Objectives:**
  - Flatpak, the per-user Flathub remote and masked Fedora repos in the installed gui
    image;
  - persistent dev signing;
  - publish dev images to GHCR;
  - cross-build update and rollback.
- **Likely changes:**
  - `scripts/build-image`, `scripts/signing-keys` and `scripts/dev-keys` (use the
    environment key when present, throw-away otherwise);
  - `.github/workflows/vdi.yml` and `build.yml` publish jobs (`environment:`, minimal
    permissions);
  - `tests/vm/test_update.py` (cross-build) and `tests/vm/test_vdi_persistence.py`;
  - ADR-0015 (persistent signing identities).
- **Acceptance:**
  - after two full power-offs: Chrome, settings, wallpaper, files and onboarding state
    are present;
  - an update from run B is applied over run A's VDI;
  - an untrusted-key image is refused;
  - rollback works and user data is intact;
  - the account survives the update (`/etc` merge);
  - a broken update falls back without data loss (§11a);
  - the backup and recovery section of the guide is written.
- **Security:**
  - secret-scope test: the secret is referenced only by the publish job;
  - gitleaks;
  - an artifact scan that no PEM private key is in any artifact.
- **Risks:**
  - `/etc` merge conflicts for passwd and shadow. Mitigation: test; fallback to
    `systemd-userdb` drop-ins in `/var`.
- **Done:** the persistence and update suites are green on two separate runs.

### M10: Hybrid desktop UX

- **Objectives:** the §4 spec: top bar, Quick Settings plasmoid, shortcuts, tiling
  layouts, Dolphin and KRunner defaults, spectacle, Light/Dark switch.
- **Likely changes:**
  - `image/rootfs-gui/usr/share/plasma/look-and-feel/org.aegisos.desktop/**`;
  - new `plasmoids/org.aegisos.quicksettings`;
  - `/etc/xdg` defaults (kglobalshortcutsrc, kwinrc tiling, dolphinrc, krunnerrc);
  - `rpms.in.yaml` gui (spectacle);
  - `scripts/make_plasma_theme.py` (top-bar frame);
  - `tests/vm/test_gui.py` and a new `test_desktop_ux.py`.
- **Design bar (amendment 5):** an original AEGIS composition, not stock panels.
  - Custom AEGIS Glass frames for the top bar, dock and Quick Settings.
  - An AEGIS SDDM login theme and splash.
  - Refined icon set choices, spacing and type scale from the tokens; consistent hover
    and press motion.
  - Glass effects follow the active profile, so they stay performance-aware.
- **Acceptance:**
  - each shortcut does its action (QMP keys, KWin window state);
  - snapping produces the expected geometry;
  - Quick Settings toggles change real state;
  - no QML errors;
  - frame and CPU budgets met;
  - **screenshots at 1366×768, 1920×1080 and the largest offered mode, in Dark and
    Light, in Performance and Balanced Glass**, inspected and placed in
    `docs/architecture/v3-screenshots/`;
  - the owner reviews them before the milestone closes.
- **Parallel:** yes, with M8 and M9. It touches only `rootfs-gui` desktop files and
  plasmoids, not storage.
- **Done:** UX suite green; owner review of the screenshots.

### M11: Native interactive welcome experience

- **Depends on:** the M8 `apps/` build stage and M10's shortcuts and dock (for scene
  content).
- **Likely changes:** `apps/aegis-welcome/**` (C++/QML), KWin script under
  `/usr/share/aegis/welcome/kwin/`, autostart entry, `tests/vm/test_welcome.py`.
- **Cinematic direction (amendment 6):**
  - The AEGIS mark assembles from glass shards over a parallax wallpaper.
  - Scenes cross through shared-element transitions.
  - Each exercise shows an animated ghost hint until done.
  - An in-app drag-and-drop exercise: drag an app icon onto a dock replica, then pin
    the real app.
  - The reduced-motion variant swaps motion for fades.
- **Acceptance:**
  - each scene completes from **real input** sent through QMP (open the launcher, snap
    a real Dolphin window, switch the profile);
  - the drag-and-drop exercise completes with pointer events (QMP `input-send-event`
    press, move, release);
  - every scene can be completed with the keyboard alone (Tab, Enter, Esc, arrows);
  - scene transitions are recorded (frame meter during transitions, screenshots per
    scene);
  - skip and replay work;
  - reduced motion results in zero-duration animations;
  - the completion state persists across a reboot (VDI);
  - offline mode works;
  - the software-renderer path stays within the frame budget.
- **Security:** no privileges; the KWin script is read-only (it only reports geometry);
  no network except the optional install step.
- **Parallel:** with M12 after M8 (separate `apps/` subdirectories).

### M12: AEGIS App Center

- **Depends on:** the M8 build stage and M9 (Flatpak in the installed image).
- **Likely changes:** `apps/aegis-appcenter/**`, desktop entry, dock pin,
  `tests/vm/test_appcenter.py` (network), unit tests for permission mapping.
- **Acceptance:**
  - search finds Chrome;
  - details show the verified badge and permissions;
  - install with progress, then the app launches; uninstall works;
  - an update is detected (install an older commit, then update);
  - errors are shown for no network and a full disk (small loop mount for the test);
  - installs survive a reboot;
  - no polkit prompt ever appears.
- **Parallel:** with M11.

### M13: Performance, accessibility, regression, release

- **Objectives:** the §7 budgets; an accessibility pass (keyboard-only walkthrough of
  setup, welcome and App Center); the full regression matrix; publish the
  `aegis-os-v3-vdi` artifact (prod key, protected environment, approval); release notes.
- **Acceptance:**
  - all suites green on one commit;
  - budgets met or deviations documented;
  - the owner's VirtualBox check-list returned (setup, resize, full screen, Chrome,
    reboot persistence, update).

### M14 (future, not blocking v3): graphical installer from the Live ISO

- Live-session installer driving `bootc install to-disk`. It must refuse non-virtual or
  non-empty disks unless confirmed twice, and is reviewed separately.

### Dependency graph

```
M8 ──► M9 ──► M12 ──┐
 │                  ├──► M13 ──► v3 release
 ├──► M11 ──────────┤
M10 (parallel) ─────┘          M14 later, independent
```

Conflict zones: `rpms.in.yaml` and the lock (serialise lock bumps through one
update-inputs run per milestone), `Containerfile.gui`, `test_gui.py`.

## 11. Release and artifact strategy

- **`aegis-os-v3-vdi` artifact:** `AEGIS-OS-v3.vdi` (zip-compressed by the artifact
  upload), `SHA256SUMS`, `VIRTUALBOX_V3_GUIDE.md`, `CHANGELOG-v3.md`, `TEST-REPORT.txt`,
  `BUILD-INFO.txt`, and public Secure Boot and image-signing certificates (public only).
  Published only from a fully green run via the protected environment.
- **Updates:** dev channel `ghcr.io/ben10-games/aegis-os/aegis-gui:v3-dev`; prod
  channel after M13.
- **Long-term downloads:** artifacts expire after 14 days. GitHub Releases are proposed
  for v3, which needs owner approval: it publishes publicly and permanently.
- **Unchanged:** GUI v2 and earlier artifacts and branches; the Live ISO workflow keeps
  working for the "try it" path.

## 11a. Recovery, backups and update-failure handling (amendment 4)

Documented in `VIRTUALBOX_V3_GUIDE.md` (new "Backups and recovery" section) and tested
where possible.

- **Snapshots before risk.** Take a VirtualBox snapshot ("Machine → Take Snapshot") after
  first-boot setup, and before every update. Restoring returns the whole disk to that
  point.
- **Backups.**
  - Full: power off, then "File → Export Appliance" (OVA), or copy the VDI with
    `VBoxManage clonemedium`.
  - User files only: a host shared folder or a copy of `~/` to a second virtual disk.
  - The guide notes that snapshots are not backups: they live in the same folder.
- **Update protection** (bootc behaviour, made visible):
  - The update is downloaded and staged while the running system is untouched.
  - It is checked against the image signature policy before staging; an unsigned or
    untrusted image is refused (V-09/V-15) and the system is unchanged.
  - It becomes active only after a reboot; the previous deployment stays as a boot
    entry.
  - `/var` (homes, Flatpak apps) is shared and is never rewritten by an update or a
    rollback.
- **Update failure.**
  - If the new deployment fails to reach the desktop: choose the previous entry in
    systemd-boot (Space at boot), then `sudo bootc rollback`.
  - An AEGIS notice tells the user when the system booted into a rollback entry.
  - The guide gives `bootc status` and `journalctl -b -1` for reports.
- **Tests (M9).**
  - User data and the account are intact after: update, reboot, rollback, reboot.
  - A deliberately broken update (one that fails `aegis-verify-cmdline`) leaves the
    previous deployment bootable with data intact, in QEMU.
- **Recovery without a password.** If the only account's password is lost, the guide
  explains restoring a snapshot or attaching the VDI to the Live ISO to copy files out.
  There is no backdoor and no fixed recovery credential.

## 12. Major risks and mitigations

| Risk | Mitigation |
|---|---|
| Compiled apps (C++/Qt) need a new locked toolchain stage: lock churn, build time | One `apps-build` step, built once per run in a cached stage; only installed binaries reach the image (like `dev-policy`) |
| `/etc` merge of `passwd`/`shadow` across updates | Tested in M9; fallback `systemd-userdb` in `/var` |
| Kiosk first-boot session with KWin and SDDM | Spike first; plasma-setup if available; QEMU tests with QMP input |
| VirtualBox differences (SVGA, EFI, Secure Boot enrollment, guest tools under SELinux) | Owner check-list per milestone; `graphics-report` and `journalctl \| grep avc` output requested; nothing claimed without it |
| Flathub/AppStream API changes, network flakiness in CI | Network suite separate and retried once; offline catalogue fixture for unit tests |
| Log-tail limits hide evidence | Text summary last, few small screenshots, full artifacts |
| Secret misuse | Environments with branch rules and required reviewers; secret used by one step; scans |

## 13. Explicit assumptions and open questions

- **Assumptions:**
  - bootc's composefs backend keeps `/var` shared across deployments and merges `/etc`
    (to be proven in M9 tests).
  - VirtualBox boots the same UEFI/systemd-boot disk (likely: the Live ISO boots its
    EFI; but the VDI's systemd-boot path itself is **untested in VirtualBox**).
  - A 64 GiB dynamic VDI fits users' hosts.
- **Open questions for the owner:**
  1. ~~Dev keys~~: approved (amendment 2). Prod keys and the prod trust root: separate
     approval, to be requested at M13.
  2. GitHub Releases for permanent v3 downloads?
  3. Add packages Inter font, spectacle, Orca (screen reader)?
  4. TPM2 disk encryption: in scope for v3 or later?
  5. App Center updates: notify only, or automatic per-user updates?
  6. Should the v3 desktop image keep the development SSH server (key-only, used by
     tests), or should tests move to a test-only image variant?

## Verification of this plan

- **Per milestone:** each milestone is verified through the CI suites in §9, each run
  recorded with commit and run link in `PROJECT_STATE.md` (amendment 10). Every report
  has two separate sections:
  - "Automated (QEMU on CI)";
  - "VirtualBox (owner-reported)".
- **VirtualBox check-list:** a per-milestone VirtualBox check-list is handed to the
  owner, covering setup, resize and full screen, reboot persistence, update and
  rollback, snapshot restore, and Secure Boot state. Nothing in it is marked verified
  until the owner returns results.
- **Every commit:** the existing security suite (M1–M5), R-01/R-02, GUI v2 tests and the
  Live ISO suites keep running and must stay green (amendment 8).
- **Order:** M8 and M9 are done before M10–M12 begin integration (amendment 1). M10 may be
  developed in parallel but is merged only after M9 is green.

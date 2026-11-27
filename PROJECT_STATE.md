# AEGIS OS — project state

This file is the single source of truth for what exists and what has been verified.
It is updated in the same commit as the work it describes. A test is listed as verified
only if it actually ran and passed, with the commit and where it ran.

## 1. Resume here

- **Branch:** `claude/aegis-os-architecture-ayxptj`
- **Phase / milestone:** Phase 1. M0 to **M4 are complete** (M3 sealed boot chain,
  M4 signed updates and rollback; gate G1 passed); **M5 (input pinning,
  reproducibility, SBOM) is complete**: `build` run 44738357964 and `lint` run
  44738358019 on `cd9bf7c`. See sections 4 and 5 and
  `docs/architecture/security-baseline.md`.
- **Next task:** M6 (P1-17 metrics baseline V-12, P1-18 operations documentation,
  P1-19 exit review) on the security branch; needs the owner's go-ahead. GUI v1 is
  verified on `claude/aegis-os-gui-v1` (not merged; merging needs the owner's
  authorisation); its next tasks are in `docs/architecture/gui-architecture.md`. Input updates follow
  `docs/operations/inputs.md`. The GUI foundation (M4-GUI) is on branch
  `claude/aegis-os-gui-foundation`; GUI v1 continues on `claude/aegis-os-gui-v1`
  (see "GUI v1 track" below).
- **Reading results from a cloud session:** artifacts cannot be downloaded there (the
  storage host is blocked). Read the end of the `build` job log: the "Collect results"
  step prints `scripts/summarize-results`, with short inventories, the differences
  between golden manifests and the build, measurements and test reports last.
- **To continue:**
  1. `make static` (must pass before every commit).
  2. Push, then read the `lint` and `build` results for that commit.
  3. When an image change alters a golden manifest, copy the new entries from the
     "differences between the golden manifests and this build" block of the job log
     into `tests/golden/` in the same commit series.

### v3 track ("The Experience Update"), branch `claude/aegis-os-v3`

Owner-approved blueprint: `docs/architecture/v3-blueprint.md` (persistent VirtualBox
disk first, then hybrid desktop, onboarding, App Center, release; installer M14 later).
Branched from `claude/aegis-os-gui-v2` (`0821eb8`); not merged anywhere (needs the
owner's authorisation). User guide: `VIRTUALBOX_V3_GUIDE.md`.

- **M8 (in progress): persistent VDI and first-boot account setup.**
  - Implemented (`71bb572`): `image/Containerfile.v3` (aegis-v3 = aegis-gui + compiled
    AEGIS apps from the locked `apps-build` step + first-boot setup; SSH server disabled,
    release firewall zone; build fails if an account, password hash or SSH key is
    present); AEGIS Setup (Qt Quick, KWin-only session as the system user
    `aegis-setup`); root helper `aegis_provision.py` behind a socket only `aegis-setup`
    can open (one account, refuses afterwards); Flatpak (per-user Flathub) and VirtualBox
    guest tools moved into the gui image; `scripts/export-vdi`, `run-v3-tests`,
    `summarize-v3`; workflow `v3.yml`; `tests/vm/test_v3_vdi.py`; test-only SSH for one
    boot through a firmware credential (QEMU only).
  - Base pin renewed (`8a256cc`) to `sha256:f3afa8b1…` (probe run 45818555819): the
    previous base's selinux-policy 45.24 was only in Fedora's updates archive, a host the
    lock does not allow (update-inputs run 45817451494).
  - RPM lock regenerated on the new base (update-inputs run 45819994173, attempt 2): 660
    packages; Flatpak and VirtualBox guest tools now in the gui step, 43 packages in the
    new `apps-build` toolchain step (build stage only), `live-apps` removed.
  - v3 run 45822043552 (`e4c7405`): image built and sealed, 64 GiB disk installed, VDI
    converted (5.65 GiB, `qemu-img check` clean); Fedora's `sddm-autologin` PAM stack has
    no uid limit, so autologin of `aegis-setup` is allowed. The export then stopped on a
    false positive: the words "PRIVATE KEY" occur in the OS's own files on the disk.
    Replaced by `scripts/find_key_material.py`, which looks for this build's private keys
    themselves on the disk.
  - v3 run 45823217951 (`f41c3f7`, QEMU on VirtualBox-like hardware, not VirtualBox):
    Secure Boot suite on the v3 disk 8/8; VDI suite 6/7. Passed: VDI file (64 GiB),
    AEGIS Setup on first boot with no account, root locked, SSH server off; account
    created by typing (wheel, second request refused: "This computer is already set
    up."); login screen accepts the typed password, desktop in 4.5 s; SELinux enforcing,
    no denials, no failed units; clean power-off. Power-on to SSH 18.4 s. Persistence
    over a complete power-off: file, glass profile, wallpaper and account kept; the
    colour scheme came back empty because the test wrote only the bare key, which
    Plasma's wallpaper-accent re-apply dropped. The test now uses
    `plasma-apply-colorscheme` (as System Settings does). Screenshots: the
    Administrator label of AEGIS Setup was invisible (dark on dark), fixed; the login
    screen is still Fedora's SDDM theme (AEGIS theme in M10).
  - **M8 offline suites green: v3 run 45826914131 on `23c9e9d`** (QEMU on VirtualBox-like
    hardware, not VirtualBox): Secure Boot suite on the v3 disk 8/8, VDI suite 7/7.
    After a complete power-off: file, colour scheme AEGIS Light (set inside the session
    as System Settings does, then a wallpaper change), glass profile `full`, wallpaper
    and account kept; screenshots show the Light dock after the reboot and the
    Administrator label in AEGIS Setup. The M9 Chrome suite in that run failed before
    installing anything: the test sent the account request without the newline the
    helper waits for (fixed).
  - Repeated green: v3 run 45979036799 on `0be5ca8` (Secure Boot 8/8, VDI 7/7). Its Chrome
    suite failed again before installing anything: the request script in the test lost
    its escape sequence (a non-raw string), so Python could not parse it (fixed; the
    script is now compiled and exercised against a local socket before pushing).
  - **First experimental VDI published: v3 run 45992321699 on `4a69cef`**, every suite green
    (QEMU on VirtualBox-like hardware, not VirtualBox): Secure Boot 8/8, VDI 7/7, Chrome
    6/6 (installed in 34 s, started in 3.3 s before and after a complete power-off); no
    key material of the build's 5 private keys on the disk. Same commit: `build`
    45992321728, `live-iso` 45992321702, `lint` 45992321752 green. Artifact
    `aegis-os-v3-vdi` (2,463,384,532 bytes zipped, kept until 2026-12-11):
    https://github.com/ben10-games/AEGIS-OS/actions/runs/45992321699/artifacts/15194592920
    `AEGIS-OS-v3-0.1.0-dev-4a69cef.vdi` SHA-256
    `eb8347f09a02e06174cb9e4f5b2faba1210b51766355ef78c54ac214059b49e5` (64 GiB virtual,
    5.72 GiB allocated); sealed root digest `54dad838…`. Labelled experimental; no system
    updates in this build.
  - **Not verified in VirtualBox.** Waiting for the owner's check
    (`docs/operations/v3-virtualbox-checklist.md`). (waiting for the regenerated
    RPM lock). Not verified in VirtualBox.
- **M9 (prepared): persistent development signing (ADR-0015).** Workflow
  `dev-signing-bootstrap` (manual, v3 branch, reviewer-gated environment
  `aegis-dev-bootstrap`) creates Secure Boot PK/KEK/db and the image signing key on a
  tmpfs and stores them only as secrets of `aegis-dev-signing`; it refuses to replace
  existing secrets and prints only public halves. **Waiting for the owner:** the
  environments and the short-lived bootstrap token
  (`docs/operations/dev-signing-setup.md`). Not run yet. No production key exists.
- **M9 (written, not run yet): Chrome persists on the VDI.** `tests/vm/test_v3_apps.py`
  (network suite in `scripts/run-v3-tests`, same hosts as the Live ISO's Flatpak
  suite): account through the setup socket as `aegis-setup`, login by typing, per-user
  Flathub remote only, Chrome installed into the user installation on the btrfs disk,
  started, complete power-off, still listed and starts again, SELinux without denials.
- **GUI v2 Live ISO on the renewed base: green, after an intermittent failure.** live-iso
  runs 45822043527 (`e4c7405`) and 45823218002 (`f41c3f7`) failed 2 of 24 offline tests:
  blur still loaded a fixed 4 s after switching to Performance Glass. Run 45987212326
  (`bfe51d7`, same image inputs) passed 24/24 offline and 5/5 Flatpak, with KWin at
  35–40 % of a CPU under Performance (GUI v2: 39–45 %). KWin applies a reconfigure
  asynchronously, so the tests now wait up to 20 s for the expected effect state,
  record how long it took, and log the user's `kwinrc`, KWin's loaded effects and its
  configuration environment if it never arrives. (Correction: the 86 % quoted while
  investigating was the Flatpak suite's 4-CPU Automatic-profile measurement, not
  Performance Glass, and is not evidence of a regression.) `build` (M1–M5,
  reproducibility, GUI under Secure Boot) is green on `5c22f44` (run 45982673831).
- **M9 Chrome persistence green: v3 run 45982673897 on `5c22f44`** (QEMU, not
  VirtualBox): Secure Boot 8/8, VDI 7/7, Chrome suite 6/6. Per-user Flathub only;
  Chrome installed in 31 s into the user installation on the btrfs disk
  (`/state/os/default/var`), started in 3.3 s; after a complete power-off still installed
  and started in 3.3 s; no SELinux denials. Chrome showed "Restore pages?" because the
  test ends Chrome by stopping its service. The VM had no swap (zram) active: to be
  checked in M13.
- **M9 update and rollback on the VDI, same-build form: green.** v3 run 46015720076 on
  `0d1bd3b` (QEMU on VirtualBox-like hardware, not VirtualBox), `tests/vm/test_v3_update.py`
  6/6, besides Secure Boot 8/8, VDI 7/7, Chrome 6/6. Version A (the VDI) with account,
  Chrome, a file, AEGIS Light, Performance Glass and wallpaper. Unsigned update refused
  by the image's policy ("A signature…"), untrusted-key update refused (cryptographic
  verification failure), nothing staged either time. AEGIS-signed update to version B
  staged in 14 s and booted (bootc: B booted, A as rollback); everything kept, Chrome
  starts, no SELinux denials. `bootc rollback` to A: everything kept, Chrome starts, no
  denials. A and B were signed with the same per-build key in one run; the cross-build
  form (A from an earlier run) needs the persistent development identity.
  Found: Chrome's first start opens KDE's wallet first-use wizard (no `kwallet-pam`, which
  would open the wallet with the login password); asking the owner to approve the
  package.
- **M9 signing bootstrap: not run; owner setup not confirmed.** The workflow could not
  be started: GitHub returns 404 for it, because a workflow with only a manual trigger
  can be started only from the default branch. It now starts from a v3-branch commit
  containing `[bootstrap-dev-signing]` (still behind the owner's reviewer approval) and
  first checks that `aegis-dev-signing` is branch-limited and `aegis-dev-bootstrap`
  requires a reviewer. Waiting for the owner: `docs/operations/dev-signing-setup.md`
  steps 1–3 (the token now also needs Environments: Read-only).
  **Incident, run 46015720213 (`0d1bd3b`):** the commit message that described the
  marker contained it, so the bootstrap job started; `aegis-dev-bootstrap` did not exist,
  GitHub created it unprotected, and the job ran without review. It stopped at its first
  line (no token): no key was generated, nothing was stored or printed. Hardened: the
  workflow now starts only when `keys/dev/bootstrap-request` changes and the commit
  subject begins with the marker, and a secret-free preflight job (actions: read) checks
  both environments' protection before the key job can exist. The owner should open the
  now-existing `aegis-dev-bootstrap` and add the reviewer and branch rule (step 2).
- **Packages for M10/M11/M13 locked** (update-inputs run 46015922956, 682 packages):
  spectacle (GPL-2.0-or-later), rsms-inter-fonts (OFL-1.1), orca (LGPL-2.1-or-later)
  with their dependencies: speech-dispatcher (GPL-2.0-or-later/LGPL), espeak-ng
  (GPL-3.0-or-later), liblouis and brlapi (LGPL-2.1-or-later), pyatspi, dasbus, kf6-purpose,
  kquickimageeditor, accounts-qml-module, kf6-bluez-qt (LGPL), pcaudiolib (GPL-3.0+), libao
  (GPL-2.0+), dotconf (LGPL-2.1): about 33 MB, Fedora-signed, `fedora`/`updates` only.
  Also picked up: llvm-libs 23.1.6, pipewire 1.6.12.
- **M10 first CI run, v3 run 46021359536 on `4ff9c0c`:** desktop suite 12/14; other v3
  suites green. Passed: the greeter runs the AEGIS theme; a 36 px full-width top bar and
  the centred dock at 1024, 1366, 1920 and 4096 px; Meta+A opens Quick Settings (583 kB
  of the screen changed); Meta+E, Ctrl+Alt+T, Meta+I, Meta+Shift+S start their
  applications in 0.1–0.3 s; Meta+Left/Right snap to exact halves; Quick Settings actions
  change the real settings; no QML errors, no denials. Failed: Meta+Up on a half tile made
  a quarter tile (KWin's behaviour; Meta+PgUp maximises, test and tour hint corrected);
  font and Alt+Tab defaults read outside the session (test now reads inside it). Same
  commit: `build` 46021359460 and `live-iso` 46021359978 green with the new layout.
- **M10 hybrid desktop: automated suite green, v3 run 46037336379 on `6b6598c`** (QEMU,
  not VirtualBox): desktop suite 14/14 (Inter and the Alt+Tab grid in effect in the
  session; Meta+PgUp maximises), with Secure Boot 8/8, VDI 7/7, performance 6/6, Chrome
  6/6, update and rollback 6/6 on the same image. Screenshots inspected: AEGIS login screen
  (glass card, initial, name, focused password field, time and date, Restart and Shut
  down), Dark and Light desktop at 1920x1080, Quick Settings. Owner review of the
  screenshots and VirtualBox check outstanding.
- **M10 hybrid desktop (details):** top bar (AEGIS mark with
  the active application, global menu, search Meta+S, tray with notifications, AEGIS Quick
  Settings Meta+A, clock) and the floating dock; Quick Settings (Dark/Light, Liquid Glass
  profile, Night Light, Do Not Disturb, screenshot, network, sound, display, lock) through
  `/usr/libexec/aegis/quick-settings` as the user; AEGIS login screen (SDDM theme `aegis`);
  Inter, Alt+Tab thumbnail grid, edge snapping; shortcuts Meta+I settings, Meta+Tab
  overview, Meta+Shift+S screenshot. Test: `tests/vm/test_v3_desktop.py`.
- **M11/M12 first CI run, v3 run 46023524801 on `6cfb421`:** both applications compile
  and are in the image; Secure Boot 8/8, VDI 7/7, Chrome 6/6, update and rollback 6/6
  with them. The tour starts by itself 0.2 s after the desktop on the first login, loads
  its KWin watcher, renders without QML errors (screenshot inspected); opening animation
  CPU: aegis-welcome 34 %, KWin 76 % of one CPU (2 CPUs, software rendering). All later
  tour and App Center tests failed because the test helper that starts the applications
  combined `systemd-run --wait` with `--no-block` (fixed).
- **v3 run 46031049611 on `e634dbf`:** tour restart and resume now pass; the launcher step
  was not detected (the watcher compared the Wayland class with "plasmashell"; it is
  "org.kde.plasmashell", fixed); AT-SPI found no controls in the tour or the App Center
  (diagnostics added: the helper lists the applications on the accessibility bus and
  searches all of them). Performance repeated: reboot to login 7.5 s, boot 9.3 s, password
  to desktop 4.5 s; opening animation CPU this time 14 % (tour) / 38 % (KWin).
- **Found by the M11 tests (v3 run 46040929112 on `a6174f6`): Orca could not start.** The
  tour's launcher and Files steps now complete from real events, but importing pyatspi
  (Orca's accessibility library, also used by the tests) failed: the DBus-1.0 typelib
  comes only with gobject-introspection, a weak dependency the build does not install.
  Added (update-inputs run 46051406945: one package, 0.13 MB, LGPL, `fedora`); the gui
  image build now fails if pyatspi does not import.
- **v3 run 46052351712 on `5cd4342`:** App Center 3/6: the Flathub catalogue loads and
  search finds Chrome (1 s after the catalogue was in place); Firefox's page shows
  "Verified publisher" with the not-a-safety-guarantee explanation and its permissions;
  Chrome installs from the App Center in 37 s into the user installation (no system
  install) and opens. Tour: launcher, Files, search and security steps complete from real
  input. Fixed for the next run: drag and drop (QML id clashing with `palette`, drop read
  after release), the practice window (`dolphin --new-window`), the Light/Dark tiles'
  accessible role, App Center progress text (flatpak prints no percentages without a
  terminal), and test-side issues (commit check, replay while running, stale page).
- **M11 Welcome to AEGIS:** `apps/aegis-welcome` (Qt Quick
  with a C++ core), seven scenes: AEGIS awakens (the mark assembles from glass shards),
  Meet your desktop (real launcher and Files, drag-and-drop practice dock), Control your
  workspace (move, resize, snap, maximise and minimise a real window, completed from
  KWin's reports through `watch.js`), Make it yours (live Dark/Light, Liquid Glass,
  wallpaper, Undo), Explore applications (offline sample catalogue; "verified publisher"
  explained as not a safety claim), Security and privacy (real state, honest about Secure
  Boot off), You're ready. Back/Next/Skip, Alt+arrows, Escape; progress in
  `~/.local/state/aegis/welcome.json`; first-login autostart, replay from the launcher;
  reduced motion (KDE setting or switch); lite visuals under Performance Glass; no
  privileges. Test: `tests/vm/test_v3_welcome.py` (QMP keyboard and a real pointer drag,
  AT-SPI for the other controls, D-Bus state, CPU during the opening animation).
- **M12 AEGIS App Center (written, first CI run pending):** `apps/aegis-appcenter` (Qt Quick
  with a C++ core) on Flatpak's own tool, always `--user` (no administrator rights):
  Flathub AppStream catalogue (search, categories, icons, screenshots, description,
  developer, licence), "Verified publisher" with its explanation (not a safety claim),
  permissions in plain words with risk levels, install with progress, open, update one or
  all, remove, plain error messages with Try again; a daily user timer only announces
  updates (never applies them). Test: `tests/vm/test_v3_appcenter.py` (network suite).
  Not tested: a full disk.
- **M13 measured performance, v3 run 46027289849 on `86cfe67`** (QEMU with KVM on a GitHub
  runner, VirtualBox-like hardware, 2 CPUs, 4 GiB, software rendering; not VirtualBox):
  first start to AEGIS Setup 16.8 s; reboot to login screen 7.6 s; boot 9.6 s (kernel
  0.9 s, initrd 2.7 s, userspace 6.0 s, graphical.target after 6.0 s); password to desktop
  4.6 s; idle CPU KWin 0.0 %, plasmashell 0.1 % (30 s); memory used 955 MiB of 3894 MiB
  (plasmashell 448 MB, KWin 268 MB RSS); zram swap active (zram0, 1.9 GiB, zstd); window
  shown after start: Files 2.9 s, Welcome tour 3.0 s, App Center 2.8 s. Performance suite
  6/6. Desktop suite 13/14: Meta+PgUp maximise passes; Inter and the Alt+Tab grid were not
  applied (Plasma ignores those keys in a look-and-feel package), now set in `/etc/xdg`.
- **M13:** in progress.

### GUI v2 track (Liquid Glass 2.0, VirtualBox display, performance), branch `claude/aegis-os-gui-v2`

Owner request after VirtualBox use: laggy desktop, basic look, no full-screen resizing.
Branched from the Live ISO branch (`89cff21`); not merged anywhere (needs the owner's
authorisation). Design and diagnosis: `docs/architecture/gui-v2.md`; release notes:
`CHANGELOG-GUI-v2.md`; user guide: `VIRTUALBOX_GUIDE.md` sections 3a and 8.

- **Diagnosis (QEMU, VirtualBox-like hardware, 2 CPUs; not VirtualBox):** KWin composites
  with OpenGL ES on llvmpipe (no render node). With a glass popup over moving content KWin
  used 113–116 % of one CPU in Balanced/Full Glass against 39 % in Performance Glass
  (runs 45604938784 and 45608395419), 95th-percentile frame time 23–25 ms against 18 ms,
  worst frame 100–109 ms against 57 ms; frame rate 57–59 fps in all. Without glass over
  the animation: 33–35 % in every profile. 4 CPUs: 59.6 fps. Idle: KWin 1.8 %,
  plasmashell 0.1 %, 1.34 GB used. The QEMU card's `vmwgfx` refusal and simpledrm fallback
  were recorded earlier (run 45204188680). Plasma 6.8 has no X11 session.
- **Implemented:** rendering profiles (Full Liquid Glass, Balanced Glass, Performance
  Glass, Automatic: Performance on llvmpipe, Balanced otherwise) applied at login, AEGIS
  Appearance utility, graphics-report and AEGIS Frame Meter; Baloo off; AEGIS Glass
  Plasma theme (generated, adaptive to AEGIS Dark/Light, translucent and opaque variants,
  edge highlights, sheen, shadows, task indicators), AEGIS Light scheme, wallpaper accent,
  borderless Breeze with large shadows, dock that dodges windows; Kickoff launcher (the
  Application Dashboard is not in this Plasma build); Fedora's VirtualBox guest tools 7.2.22
  in the Live ISO (update-inputs run 45596097400) and the live 1920x1080 helper skipped
  inside VirtualBox.
- **Tested in CI (QEMU):** renderer identification and automatic profile; switching all
  profiles (KWin blur loaded or not, animation factor); launcher click and search;
  resolution changes 1366x768, 4096x2160 (largest offered) and 1920x1080 with the dock
  centred at the bottom; VirtualBox units installed and skipped outside VirtualBox; idle
  use; Chrome install and start; all earlier Live ISO checks (SELinux enforcing, no
  denials, security dashboard, admin password, network, audio, clean power-off). Sealed
  GUI image (`build`): blur loaded under Full Liquid Glass.
- **Published:** `live-iso` run 45611819540 on `a0df15a`: offline suite 24/24, Flatpak
  suite 5/5; artifact `aegis-os-gui-v2-live-iso` (ISO, SHA256SUMS, VIRTUALBOX_GUIDE.md,
  CHANGELOG-GUI-v2.md, BUILD-INFO.txt, TEST-REPORT.txt), kept until 2026-12-09.
  `AEGIS-OS-GUI-v2-Live.iso` SHA-256
  `640aaae8a6827a358c6cabb558775b5c0bcf830828696df216614ed9f5678c02`, 1,497,243,648 bytes.
  Same run: glass popup over animation KWin 117 % (Balanced) / 115 % (Full) against 45 %
  (Performance); idle KWin 1.5 %, 1.35 GB used.
- **Not verified:** real VirtualBox (resize with the guest tools, full screen, VMSVGA
  rendering, 3D acceleration), refraction (not implemented), hardware-GPU performance.
- **Bugs found on the way:** Fedora's Qt drops `console.log` (run 45597365211);
  `kscreen-doctor` aborts outside the session environment (45601312768); the Application
  Dashboard is absent (45601312768); QEMU's standard VGA rounds 1366 to a 1360-pixel
  framebuffer (45608395419).

### Live ISO track (VirtualBox), branch `claude/aegis-os-gui-live-iso`

Owner request: a UEFI-bootable graphical Live ISO (`AEGIS-OS-GUI-Live.iso`) that boots
in Oracle VirtualBox straight into the AEGIS desktop. Branched from GUI v1 (`b7f76d4`);
not merged anywhere (merging needs the owner's authorisation).

- **Design** (`docs/architecture/live-iso.md`): the live root is the unsealed graphical
  root filesystem `aegis-gui-rootfs` plus `image/rootfs-live` (`image/Containerfile.live`),
  labelled with its own SELinux policy and packed into a SquashFS; dracut `dmsquash-live`
  with an overlayfs RAM overlay; Fedora's signed shim and GRUB from the builder (same
  pinned base) in an El Torito UEFI image; the AEGIS kernel arguments in the menu.
  Unprivileged `aegis` account with automatic login; a per-boot random root password shown
  only on the text console. Not sealed, no AEGIS Secure Boot chain, no updates: listed in
  `VIRTUALBOX_GUIDE.md` section 7.
- **Inputs:** `live` step (dracut-live, fuse, parted) and xorriso in the builder; lock
  from `update-inputs` run 45184810800 (9 packages added, nothing else changed).
- **CI:** workflow `live-iso` (build, structure checks, boot in QEMU on VirtualBox-like
  hardware: i440FX, SATA CD-ROM, VMware SVGA II 128 MB, e1000, PS/2 + USB tablet, HDA).
  The ISO is published as `aegis-os-gui-live-iso` only after every test passed.
- **Verified:** `live-iso` run 45200734168 on `8609b75`, 16 of 16 tests (KVM). ISO 1.39 GiB
  (1,487,904,768 bytes). UEFI El Torito image with Fedora-signed shim/GRUB; power-on to
  SSH 23 s. Live root on overlay over SquashFS, SELinux enforcing with correct labels, zero
  denials, zero failed units; `aegis` (uid 1000, not in wheel, password locked) logged
  in to Plasma on Wayland by SDDM; 1920x1080 (bochs-drm, set by the login helper);
  Ctrl+Alt+T and typing into Konsole; right click opens the desktop menu; Dolphin and
  System Settings; dashboard values match the live state (no QML errors); e1000 network
  connected; HDA sink present; per-boot root password: root-only issue file, `su`
  accepts it and refuses a wrong one; clean power-off. Second boot with QEMU's VMware SVGA
  II device: Plasma session started, no failed units; run 45204188680 shows why the
  screen could not be checked there: `vmwgfx` refused QEMU's SVGA v2 device ("Hardware
  has no pitchlock", probe error -38) and the session ran on simpledrm (firmware
  framebuffer). Whether vmwgfx binds on VirtualBox's VMSVGA is not verified.
- **Published:** `live-iso` run 45204188680 on `4e2fd10` (16/16), artifact
  `aegis-os-gui-live-iso` (ISO SHA-256 `17abfe84533ecf45ea25faf99698dda089f45f9e3742f5e5e2cf19ee90dcb003`,
  1,487,904,768 bytes), kept until 2026-12-07. Screenshots inspected:
  `docs/architecture/live-iso-screenshots/`.
- **Owner feedback:** the ISO booted in Oracle VirtualBox on Linux Mint (owner report).
- **Flatpak (owner request):** `flatpak`, `flatpak-selinux` and `fedora-flathub-remote`
  in the live root only (locked step `live-apps`, update-inputs run 45402156615, which also
  took Fedora updates of kwin, openssh and edk2-ovmf). Flathub is a remote of the live
  account's own installation (`aegis-flathub-user-remote`, a user unit, from the file in
  Fedora's signed package; its Fedora filter line is dropped); no system remote (Fedora's
  'fedora' remote deleted at build time, `flatpak-add-fedora-repos.service` masked).
  The RAM overlay may use 75% of memory (`aegis-live-overlay-space.service`; systemd's
  default 20% was 779 MB). KWallet is off in the live session. Verified: `live-iso` run
  45412268908 on `3ca1749`, offline suite 16/16, network suite 4/4:
  `flatpak install --user flathub com.google.Chrome` in 22 s (Chrome 158, installation
  "user", 2.6 GB in the overlay of 2.9 GB in a 4 GiB VM), Chrome running in the session
  (screenshot inspected), SELinux enforcing, zero denials, zero failed units. With Chrome
  running only about 80 MB of memory remained available: 8 GiB is recommended. Installed
  applications are lost at power-off (persistence is a separate milestone). The network
  suite reaches dl.flathub.org and Google's download server (owner request).
- **Published with Flatpak:** `live-iso` run 45415843543 on `1883126` (16/16 offline, 4/4
  Flatpak; Chrome 158.0.8127.88 installed with --user in 32 s), artifact
  `aegis-os-gui-live-iso`, ISO SHA-256
  `77d9168783459016e090756a111fa1a5421d4892366b61efd69798ab62014e7b`, 1,495,891,968 bytes,
  kept until 2026-12-08.
- **Not verified:** Oracle VirtualBox itself (no VirtualBox on the runners; would need a
  new download host), the desktop as drawn on VMSVGA, Secure Boot, the `nomodeset` entry.
- **Bugs fixed on the way:** CI runs 45185892320 (`/mnt` scratch disk absent),
  45189500261 (QEMU's VMware SVGA emulation does not show the desktop; Secure Boot shown as
  "unknown"; su check), 45194735654 (hard links of the ostree object store gave system
  files `default_t`; the label check stopped the build), 45197563591 (escape sequence
  in su output).

### GUI v1 track (bootable graphical desktop), branch `claude/aegis-os-gui-v1`

Authorised by the owner on 2026-11-20. This branch starts from the M4-GUI foundation
(`1f5d04c`) and merges the security branch at `078ae06` (M4 and M5 complete), so the
graphical image is built from the locked RPM inputs, without network, like every other
image. The security branch is not changed by this work and nothing is merged back
without the owner's authorisation.

- Integration (merge commit): the Plasma packages become the `gui` install step of
  `image/packages/rpms.in.yaml`; the QEMU virtio display modules join the `builder` step;
  `scripts/seal-image` is folded back into `scripts/build-image`.
- First resolution (`update-inputs` run 44748085322): 589 RPMs, all verified; review
  found `openh264` from the Cisco-hosted `fedora-cisco-openh264` repository. Refused:
  the resolver disables that repository, the `gui` step names Fedora's stub
  `noopenh264`, and `scripts/rpmlock.py` now refuses any package not from `fedora` or
  `updates`. Re-resolved by `update-inputs` run 44748846864: 589 RPMs (365 `fedora`,
  224 `updates`), all verified (size, SHA-256, header, Fedora signature), cache tag
  `lock-2e7405ca645f39d9`; reviewed: the 75 earlier packages unchanged, 2 new builder
  packages (QEMU virtio display modules), 512 `gui` packages including `noopenh264`.
- Downloadable image (Stage B): `scripts/export-qcow2 --gui` → `out/release-gui/`
  (QCOW2, `run-aegis-gui-vm.sh`, `LOCAL_GUI_VM_GUIDE.md`, `IMAGE-INFO.txt`,
  `SHA256SUMS`), published as artifact `aegis-os-gui-qcow2` only after every test in
  the GUI job passed. Login: the launcher creates user `aegis` (uid 1000, `wheel`) at
  first boot through systemd credentials, with a random password kept next to the image
  and only its SHA-512 hash passed to the VM; the image itself has no user. Tested by
  `tests/static/test_local_gui_launcher.py` (fake QEMU) and in CI by
  `tests/vm/test_local_gui_image.py` (the exported file booted with the launcher). Not
  run yet.
- Visual design and components (Stages C to E), all in the image under `/usr` except
  `/etc/xdg/kwinrc`:
  - `org.aegisos.style` QML module (`/usr/lib64/qt6/qml/org/aegisos/style`): design
    tokens (colour, opacity, blur, radii, spacing, typography, shadow, motion), three
    glass materials with opaque fallbacks for the software renderer, and the
    `GlassSurface` and `StatusRow` primitives.
  - Glass from KWin itself: blur and contrast effects on, blur strength 12, noise 2
    (`/etc/xdg/kwinrc`); no own compositor code.
  - AEGIS dock: floating, translucent, centred panel with the AEGIS mark on the
    launcher, pinned Files, Terminal and Settings, the AEGIS Security widget, tray, clock.
  - AEGIS Security Dashboard v0 (`org.aegisos.security` Plasma widget): SELinux, Secure
    Boot, sealed root and digest, command-line check, firewall, lockdown, running image;
    data from `/usr/libexec/aegis/security-status`, run as the desktop user (read-only;
    update state needs root and is shown as unavailable).
  - Control Center: Plasma's system tray (network, volume, power) is used as is; no
    AEGIS control panel yet.
  - On-screen keyboard not started (`InputMethod` empty; still installed, can be enabled).
  - New wallpaper (`scripts/make-wallpaper`, inspected).
  Tests added: `tests/vm/test_gui.py` (idle measurements, KWin effects loaded, keyboard
  absent, dock layout, dashboard facts and screenshot, application start times) and
  `tests/static/test_gui_assets.py`.
- First full GUI v1 run, `build` run 44749833133 on `84b60d0` (KVM): the graphical
  image builds from the locked inputs without network, seals, passes
  `bootc container lint` and installs. GUI job: 20 of 21 tests on the harness VM under
  Secure Boot (all 8 M3 Secure Boot / sealed-root tests pass on the GUI image), 9 of 10
  on the exported QCOW2 booted with `run-aegis-gui-vm.sh` (1920x1080 Wayland desktop,
  typed command runs as the user, network, audio device, SELinux enforcing with no
  denials, clean power-off). Failures, both fixed in the next commit: KWin loads no
  separate `contrast` effect (only `blur`, which is the backdrop; config and test
  corrected); the launcher's user had a locked password because systemd-sysusers
  imports password credentials for root only (drop-in importing
  `passwd.hashed-password.*`). Screenshots inspected: the dashboard window showed the
  compact icon, and the launcher and Security widget used the same mark (both changed).
  Measurements (4 GiB, software rendering): idle after login 900 MiB, KWin 261 MiB,
  plasmashell 405 MiB, on-screen keyboard 0 (not started), idle CPU 0.8 %; with
  Konsole, Dolphin and System Settings open 1147 MiB (M4-GUI: 1250-1267 MiB); systemd
  startup 10.6 s.
- **Second run, `build` run 44751864651 on `16afffe`: every job green.** GUI job 31 of
  31 (21 on the harness VM under Secure Boot including the 8 M3 Secure Boot / sealed-root
  tests; 10 on the exported QCOW2 through `run-aegis-gui-vm.sh`: account with working
  `sudo` and refused wrong password, root locked, Wayland desktop at 1920x1080, typed
  input, network, audio device, SELinux enforcing without denials, clean power-off);
  main job (all M1 to M5 tests on base and dev); R-01 and R-02 from two independent
  builds; Windows launcher. Artifact `aegis-os-gui-qcow2` published by that run
  (`aegis-os-gui-0.1.0-dev-16afffe.qcow2`, 2.36 GiB, SHA-256
  `0aa793081bc938e1…`). Measurements: idle after login 910 MiB, KWin 260 MiB,
  plasmashell 407 MiB, idle CPU 0.8 %; three applications open 1143 MiB. Screenshot
  inspection found the dashboard window clipping its last rows; fixed in the next commit
  (scrollable rows, larger default size).
- **Final verification, `build` run 44860719246 and `lint` run 44860719262 on
  `1aa082e`: every job green.** GUI job 31 of 31 (21 + 10, as above); main job (M1 to M5
  on base and dev); R-01 and R-02; Windows launcher. Screenshots inspected (dashboard no
  longer clipped; rows scroll, footer and Refresh visible) and kept in
  `docs/architecture/gui-screenshots/gui-v1-*.png`. Published artifact
  **`aegis-os-gui-qcow2`**: `aegis-os-gui-0.1.0-dev-1aa082e.qcow2`, SHA-256
  `8f0e589d89bb203185a560002e721ef349c6ec8aefb45bc819b1b42aab6eda5a`, retained 14 days.
  Measurements (4 GiB VM, llvmpipe software rendering, KVM): idle after login 903 MiB,
  KWin 259 MiB, plasmashell 408 MiB, on-screen keyboard not running, idle CPU 0.7 %
  over 20 s; with Konsole, Dolphin and System Settings open about 1145 MiB (M4-GUI:
  1250 to 1267 MiB); systemd startup 10.2 s; Wayland session within seconds of SSH being
  reachable. Not measured: frame times and window-visible application start times (the
  recorded start times are process start only).
- Skills used for GUI v1: `aegis-os-gui-engineering-toolkit` (Slot A; its five project
  skills from M4-GUI are in `.claude/skills/`) and `liquid-glass-ui` (Slot B; its
  material model was translated to QML tokens and KWin settings, its web code was not
  used). Slots C and D were not provided.

### M4-GUI foundation (history), branch `claude/aegis-os-gui-foundation`

Recorded as it was on that branch (it started from `fef77c4`, before M4 and M5). These
results are history; they do not show that the integrated GUI v1 branch is green.

State: **first functional graphical image, all GUI tests pass.** `build` run
44315378122 on `aa805e4`, job "Graphical development image (M4-GUI)", KVM, Secure Boot
with enrolled throw-away keys: 17 of 17 tests (9 GUI, 8 M3 Secure Boot / sealed root
against the GUI image); the main job (all M1-M3 tests on base and dev) passed in the
same run. First run with 16 of 17: 44312306345 on `163334e` (pointer test used the QEMU
key `meta` instead of `meta_l`).

Verified in run 44315378122 (`tests/vm/test_gui.py`, plus `tests/vm/test_secure_boot.py`
against the GUI image):

| Check | Result |
|---|---|
| Boot under Secure Boot into an SDDM autologin Plasma 6.8 session, `Type=wayland`, KWin and plasmashell running | pass |
| Secure Boot enforced, SELinux enforcing, **no AVC denials**, sealed composefs root, sealed command-line check active, no failed units | pass |
| Keyboard: Ctrl+Alt+T opens Konsole; a command typed on the virtual keyboard runs (file created, owned by the user) | pass |
| Dolphin and System Settings start and keep running | pass |
| Networking connected; PipeWire offers the virtual sound card ("Built-in Audio Analog Stereo") | pass |
| Restart returns to the desktop; power-off exits QEMU 0 with no failed unit | pass |
| M3 tests on the GUI image: V-04 (3), V-06 (4), sealed command-line check | pass (8 of 8) |
| Pointer: a right click on the desktop opens Plasma's context menu at the pointer (323,339 bytes of the screen change; screenshot inspected) | pass |

Screenshots (rendered in CI, recovered from the job log and inspected):
`docs/architecture/gui-screenshots/m4-gui-{desktop,konsole,dolphin,systemsettings,pointer-menu}.png`.

Measurements (4 GiB VM, software rendering, Konsole, Dolphin and System Settings open),
run 44312306345 / run 44315378122: memory in use 1250 / 1267 MiB (development image
without GUI: 498 MiB), 201 / 200 processes, systemd startup 10.1 / 13.5 s (userspace
6.2 / 9.3 s; shared-runner variation). Largest: plasmashell about 415 MB RSS, System
Settings 300 MB, KWin 277 MB, plasma-keyboard (on-screen keyboard, not needed) 266 MB.


### M5 progress (input pinning, reproducibility, SBOM)

**State: complete.** Verified on `cd9bf7c`: `build` run 44738357964 (both jobs) and
`lint` run 44738358019.

- **P1-15 lock.** `image/packages/rpms.in.yaml` → `rpms.lock.yaml`: 75 RPMs (9 base,
  1 dev, 12 dev-policy, 53 builder), each with NEVRA, size, SHA-256, repository and path;
  the lock also pins the base digest and the SHA-256 of `rpms.in.yaml`. The RPMs are
  kept in `ghcr.io/ben10-games/aegis-os/rpm-inputs` (tag `lock-d07ec828bc3dd5f7`, by
  digest in the lock). Resolved and verified by `update-inputs` runs 44731157775 (74
  RPMs) and 44737897215 (+ libfaketime; reviewed diff: one line).
- **Fail closed.** Every build fetches the cache by digest and checks size, SHA-256,
  header identity and Fedora signature of every RPM (`digests signatures OK` with
  `RPM-GPG-KEY-fedora-45-primary` from the base image); all image and builder builds
  run with `--network=none` and all repositories disabled.
- **Negative tests on real RPMs** (`scripts/test-inputs`, in every build and in
  `update-inputs`): changed byte; changed byte with a forged lock entry (refused by the
  signature check); missing RPM; extra RPM; another genuine Fedora package under a
  locked name with a forged entry (refused by the header check); stale lock;
  unavailable cache image; offline install with a dependency removed. All refused, with
  positive controls. Plus 41 static tests in `tests/static/test_rpm_lock.py`.
- **R-01 pass, R-02 pass, R-03 reported** (job "Two independent clean builds", run
  44738357964): build A in the checkout with root's default container storage, build B
  in a fresh clone on `/mnt` with its own storage, its own input fetch and verification
  and its own builder container; shared: the commit, the registry and the throw-away
  keys. R-01: identical base digest and image ID, lock, RPM files, builder inputs and
  installed package sets (NEVRA + SIGMD5) of builder, aegis-base and aegis-dev. R-02:
  identical composefs digests — aegis-base `38a7d42b0742…`, aegis-dev `9c1131b8d2d9…`.
  R-03: image IDs differ; 75 of 76 (base), 81 of 82 (dev), 65 of 66 (builder) layers are
  identical; not gating in Phase 1, cause not investigated further.
- **B-07, SBOM part: pass.** SPDX 2.3 per image (syft 1.27.1, pinned by digest): valid
  structure, RPMs from the image's database equal the golden list (B-02) by name and
  count, every locked package present in its locked version. The `cosign verify` part
  of B-07 is not run: published signatures are verified with the container signature
  policy (`scripts/publish-images`, run 44330064081), and the SBOM is not yet attached
  to published images.
- **Vulnerability report (report only):** grype 0.104.2 with database schema v6.1.10
  built 2026-11-20T06:21Z; 348 matches per image (91 distinct vulnerability/package
  pairs), all Go modules inside shipped
  binaries (grype has no Fedora RPM feed). Fedora's own advisories (dnf5 5.4.8, `updates`
  metadata of 2026-11-20 07:46): 9 package updates in 5 security advisories newer than
  the base pin (tpm2-tss, c-ares, p11-kit, xfsprogs (Important), criu). Scan times are
  in `out/sbom/vulnerability-report.txt` of each run.

Reproducibility fixes found by measuring (each a CI run):

| Run | Difference between the two builds | Fix |
|---|---|---|
| 44731480599 | dnf's transaction-history WAL/SHM files; the signed boot loader | remove the WAL/SHM files with the other package-manager leftovers |
| 44735052522 | only the signed boot loader: identical unsigned content, `signingTime` attribute differs | sign with sbsign's clock fixed at the commit time (libfaketime) |
| 44738357964 | none | — |

Other iterations: dnf 5 has no `--destdir` for `install` (run 44729805862); repoquery
needs real tabs (44729967506); Fedora 45 keeps its release keys in
`/usr/share/pki/rpm-gpg` (44730219961); dnf reports mirror URLs (44730658638);
`openssh-clients` is already in the base (44730882284); V-10 DNS failed once after the
builder was built offline (44731480599) and passes since the VM test container gets an
explicit loopback `resolv.conf` (the exact cause was not isolated); syft names the RPM
database `/usr/share/rpm/rpmdb.sqlite` and also reads an older copy kept in the base
image's `/sysroot/ostree` objects (44735052522).

### M4 progress (signed updates and rollback)

Verified in `build` run 44319072870 on `a7cd392` (KVM, Secure Boot with the run's
throw-away keys): 25 image tests and 83 of 83 VM tests, including:

| Test | Evidence |
|---|---|
| V-15 unsigned update refused, nothing staged | `bootc switch ...aegis-dev:v3`: "A signature was required, but no signature exists" |
| V-15 update signed by an unknown key refused, nothing staged | `bootc switch ...aegis-dev-untrusted:v4`: "cryptographic signature verification failed: invalid signature" |
| V-13 signed v2 staged; after reboot the running command line carries v2's sealed digest, v2's marker exists, Secure Boot, SELinux enforcing, command-line check active, no failed unit | `bootc status`: booted `ghcr.io/ben10-games/aegis-os/aegis-dev:v2`, `imageDigest sha256:8226608d…` |
| V-14 `bootc rollback` and reboot: v1's sealed digest again, marker gone, same security checks | `bootc status`: booted `localhost/aegis-dev:latest` |
| V-09 sentinels in `/etc` and `/var` survive update and rollback | |

How it works: `/etc/containers/policy.json` (from `policy/containers/`) rejects every
image by default and accepts `ghcr.io/ben10-games/aegis-os` only with a sigstore
signature by the AEGIS key, whose public half is sealed into
`/usr/share/aegis/keys/`. Keys are generated per run (`scripts/signing-keys`). The test
registry (`tests/vm/harness/registry.py`) runs offline in the test container; the guest
uses it only as a registries.conf mirror of the real repository name, so the image's own
policy is exercised unchanged. Assumption A5 (policy enforced on the composefs backend)
is confirmed.

Gate G1: install, Secure Boot, upgrade, rollback and tamper rejection all passed in VMs
of the same run (V-04 to V-07, V-13 to V-15). ADR-0004 is Accepted.

Signed publishing (P1-13): `scripts/publish-images` pushes `aegis-base` and `aegis-dev`
to `ghcr.io/ben10-games/aegis-os/aegis-{base,dev}:git-<commit>` signed with the run's key,
refuses to overwrite a tag, and verifies the published signature with the run's public
key (must pass) and the untrusted key (must fail). Runs only on the default branch, on
request, after every test passed. **Verified** in `build` run 44330064081 on `7dd30ce`
(`lint` run 44330063820 green): all 25 image and 83 VM tests passed, then

- `ghcr.io/ben10-games/aegis-os/aegis-base:git-7dd30ce82a91@sha256:ef5112408e19c5358b89e1217443f851ac398d770b761b738076f8f81e219c09`
- `ghcr.io/ben10-games/aegis-os/aegis-dev:git-7dd30ce82a91@sha256:7b66518f22303eeb5c238706bebe71cfd7b5ccb7bfdb79f6ad841200fc9a00b7`

were published; untrusted key: "Source image rejected: cryptographic signature
verification failed"; run key: accepted. The run's public key and the references are
the artifact `aegis-os-signed-images` (kept 90 days). The same run published the sealed
development QCOW2 (`aegis-os-dev-qcow2`, until 2026-12-02), and the Windows job booted
it with the PowerShell launcher. An earlier run (44325751988) also pushed
`git-9d2e8d345279` images before its positive verification step failed; they are signed
the same way.

Iterations: run 44306277370 (golden `/etc` entry, v4 = v2), 44312412759 and
44315892051 (skopeo reuses existing blobs, so recompression never changed v4's
manifest), 44319072870 (v4 in its own repository: all pass).

### M3 progress (sealed boot chain)

**State: complete.** Every test passed on `3a07962`: `build` run 44300954850 (25 image
tests, 77 of 77 VM tests, all under Secure Boot) and `lint` run 44300954927. Gate G1
needed update and rollback as well; it passed with M4 (`build` run 44319072870 on
`a7cd392`), and ADR-0004 is Accepted.

Boot chain as built: OVMF Secure Boot with only the build's throw-away keys
→ signed systemd-boot 262 → signed UKI (ukify; command line = `kargs.d` + composefs
digests) → composefs root with fs-verity → SELinux enforcing →
`aegis-verify-cmdline.service`. Details and the four deviations from bootc's
documented pattern are in ADR-0004.

Precondition done: the base image is mirrored to
`ghcr.io/ben10-games/aegis-os/fedora-bootc` with the upstream digest unchanged
(`mirror-base` run 43851534053), builds pin that copy
(`docs/operations/base-image.md`).

Iterations, for the record (each a CI run on this branch):

| Run | Finding | Fix |
|---|---|---|
| 43852846119 | UKIs signed, but install rejected the digest | diagnose |
| 44074603737 | digest views differ in directory mtimes | reset timestamps (did not help) |
| 44076988380 | lower-layer metadata wins on install; mtime-only changes are dropped | seal the from-storage digest (ADR-0004, deviation 1) |
| 44078774510 | installs and boots under Secure Boot; logind fails | label deployment state |
| 44086672654 | `/var` read-only (console diagnostics) | `rw` in `kargs.d` |
| 44090714344 | 60 of 62 VM tests pass | shutdown and label fixes, M3 tests added |
| 44093307831 | V-05 passes; SMBIOS `enforcing=0` made SELinux permissive | `aegis-verify-cmdline.service` |
| 44096629031 | SMBIOS extension now stops the machine; V-07 hit a stale copy | locate the live object |
| 44100054742 | V-07 passes; only `/var` busy at shutdown left | `var.mount` ordered before `local-fs.target` |
| 44104092316 | all services stop first; `/var` still busy | `journalctl --relinquish-var` unit |
| 44107287400 | relinquish unit never stopped; BUG-8 open | focused diagnostics |
| 44298288483 | journald is the only holder; `var.mount` has no unit file, so `RequiresMountsFor=` is ordering only and no ExecStop runs | relinquish unit requires `var.mount` and conflicts with `shutdown.target` |
| 44300954850 | all 77 VM tests pass; nothing holds `/var` at unmount | BUG-8 closed |

### Local VM image (owner request, done)

`LOCAL_VM_GUIDE.md` is the user-facing document. The `build` workflow exports the
`aegis-dev` disk as compressed QCOW2 (`make export`), tests the exported file, and
publishes it as artifact **`aegis-os-dev-qcow2`** only when every test in the job
passed, and only on a manual run ("Run workflow") or when the head commit message
contains `[publish-image]`. Artifacts expire after 14 days.

Verified in run 43719668136 on `aafc33a` (base image pin of 2026-11-15):

- Linux job: 14 image tests and 62 VM tests passed (the 55 M2 tests plus 7 for the
  exported image). The exported file was started with `local-vm/run-aegis-vm.sh`
  (QEMU 11.1.3, Fedora OVMF, KVM, snapshot mode): automatic root login on the serial
  console, SSH with a key passed at launch, system state `running`, SELinux enforcing,
  0 AVC records, root password locked, power-off with exit code 0, SHA-256 equal to
  `SHA256SUMS` before and after.
- Windows job (`windows-launch`, Windows Server 2025, QEMU for Windows 11.1.0,
  software emulation): artifact downloaded, checksums verified, started with
  `local-vm/run-aegis-vm.ps1`; console login after about 2.5 minutes, SSH login,
  SELinux enforcing, power-off with exit code 0.
- `tests/static/test_local_launcher.py` (in `make static`): the Linux launcher attaches
  only the image and the firmware, binds SSH to 127.0.0.1, refuses devices, directories
  and private keys.

Repeated with the final guide in run 43721070020 on `cde8eb0` (both jobs passed; `lint`
run 43721070081). That run's artifact `aegis-os-dev-qcow2` (1.24 GB, expires
2026-11-29) is the one to download.

Not verified: Windows 10/11 desktop editions, WHPX acceleration, Linux distributions
other than Fedora, physical hardware.

How login works (nothing is stored in the image):

- SSH: credential `ssh.authorized_keys.root`, passed in an SMBIOS string at launch.
- Console: credential `systemd.unit-dropin.serial-getty@ttyS0.service`, a drop-in that
  starts `agetty --autologin root`.
- The credentials `agetty.autologin=root` and `login.noauth=yes` do **not** work on this
  image (run 43718015605 showed a plain login prompt). Cause not established; a likely
  one is that agetty ignores `$CREDENTIALS_DIRECTORY` after an SELinux domain
  transition (secure-execution mode).
- The disk is exported before it has ever been booted, so it holds no SSH host keys and
  no machine identity; each user's first boot creates them.

The Windows job installs QEMU on the hosted runner with `choco install qemu`
(Chocolatey community repository, which downloads from qemu.weilnetz.de). That is an
external host the owner has not confirmed yet (section 9). Nothing from it enters the
image.

## 2. Status

| Task | Title | State | Commit / evidence |
|---|---|---|---|
| P1-00 | Environment probe | done | `6ccd8fb`; `probe` run 43459049502 green |
| P1-01 | Repository scaffold | done | `d373736` |
| P1-02 | Static tooling and lint workflow | done | `e5c0f94`; `lint` run 43458827403 green |
| P1-03 | Builder container | done | `fc13ac6`; `build` run 43460695621 |
| P1-04 | Minimal derived image | done | `fc13ac6`; `build` run 43460695621 |
| P1-05 | Disk image | done | `9c8807c`; `build` run 43460695621 |
| P1-06 | VM harness and first boot | done | `399d421`; `build` run 43460695621 |
| P1-07 | Variant split and golden manifests | done | `5d839d4`; `build` run 43547501384 |
| P1-08 | Operating system baseline | done | `e378b1e`; `build` run 43554108533 (identity, services, firewall, audit, kernel arguments, sysctl, networking) |
| P1-09 | SELinux enforcement validation | done | `c3308a8`; `build` run 43557838924 (V-08: zero denials, labels, enforcement self-test) |
| P1-10 | Ephemeral key tooling | done | `scripts/dev-keys`; keys generated per CI run, private keys only in the job workspace |
| P1-11 | Sealed image, gate G1 | done | sealed image verified on `3a07962` (`build` run 44300954850); gate G1 passed with V-13/V-14/V-15 on `a7cd392` (`build` run 44319072870) |
| P1-12 | Tamper and negative boot tests | done | `3a07962`; `build` run 44300954850 |
| P1-13 | Signing and signature policy | done | `7dd30ce`; `build` run 44330064081 (published to GHCR, signatures verified) |
| P1-14 | Update and rollback tests | done | `a7cd392`; `build` run 44319072870 (V-09, V-13, V-14, V-15) |
| P1-15 | Input pinning | done | `cd9bf7c`, `build` run 44738357964; lock from `update-inputs` run 44737897215 |
| P1-16 | Reproducibility, SBOM, vulnerability report | done | R-01, R-02 pass, R-03 reported; B-07 SBOM part pass (`build` run 44738357964) |
| P1-17 | Metrics baseline | todo | |
| P1-18 | Operations and development documentation | todo | |
| P1-19 | Phase 1 exit review | todo | |

## 3. Architecture decisions

See `docs/adr/README.md` for the index. ADR-0004 (sealed composefs backend) is
**Accepted** (gate G1 passed, `build` run 44319072870). ADR-0012 and ADR-0013 are **Open**.

Deviations from the approved blueprint:

| Deviation | Reason | Recorded in |
|---|---|---|
| GNU Make instead of `just` as the task runner | Make is preinstalled everywhere the project runs; installing extra tools in Claude Cloud was refused | ADR-0006 |
| hadolint not in the static tier yet | No pinned source for it that works in both cloud and CI; to be added with the builder container (P1-03) | this file |
| `probe` workflow also runs on pushes that change it, not only manually | Lets a cloud session obtain the result without a manual trigger | this file |
| The builder container holds test tooling only (QEMU, firmware, swtpm, pytest). Image builds and the disk install use the host's podman directly | A privileged loopback install nested inside another container is fragile; one level of nesting worked first time | this file |
| The builder container is built from the pinned `fedora-bootc` base, not a plain Fedora image | One pinned input instead of two; layers are shared with the OS image build | `build/builder/Containerfile` |
| One `build` workflow does images, disk and VM tests; there is no separate `vm-test` workflow yet | Multi-gigabyte images are not passed between jobs; split when a registry exists (P1-13) | this file |
| No `build/disk/phase1.toml`; the ESP has bootc's default size, not 2 GiB | `bootc install to-disk` creates the layout itself; the sealed UKI fits in it (M3 and M4 boot tests) | this file |
| Disk image is raw (`out/disk.raw`) with a qcow2 overlay at test time, not a stored qcow2 | Nothing consumes a standalone qcow2 yet | this file |

## 4. Completed milestones

| Milestone | Date | Evidence |
|---|---|---|
| M0 Repository and tooling (P1-00 to P1-02) | 2026-11-13 | `lint` run 43458827403, `probe` run 43459049502 |
| M1 First verified boot (P1-03 to P1-06) | 2026-11-13 | `build` run 43460695621 on `399d421`: 8 VM tests passed in 43.5 s under KVM; repeated on `a3a5004` (run 43461672095) |
| M2 Baseline configuration (P1-07 to P1-09) | 2026-11-14 | `build` run 43557838924 on `c3308a8`: 14 image tests and 55 VM tests passed (both variants, KVM); `lint` run 43557838949 green on the same commit. Same result on `3514aec` (run 43557821995) |
| M3 Sealed boot chain (P1-10 to P1-12) | 2026-11-18 | `build` run 44300954850 on `3a07962`: 25 image tests and 77 VM tests under Secure Boot, including B-06, V-04, V-05, V-06, V-07 and the boot-parameter tests; `lint` run 44300954927. G1 completed with M4 |
| M5 Inputs, reproducibility, SBOM (P1-15, P1-16) | 2026-11-20 | `build` run 44738357964 on `cd9bf7c`: 33 image tests, 83 VM tests, 8 negative input tests, R-01 and R-02 from two independent builds; `lint` run 44738358019 |
| M4 Updates (P1-13, P1-14); gate G1 passed | 2026-11-18 | `build` run 44319072870 on `a7cd392`: V-13, V-14, V-15, V-09 under Secure Boot; `build` run 44330064081 on `7dd30ce`: signed images published to GHCR and verified, all 83 VM tests |

Milestone tags `p1-m0` (`cdce239`) and `p1-m1-first-boot` (`399d421`) exist only in the
session that created them: pushing tags was refused (HTTP 403; the session may push the
development branch only). The owner can create them from the commit hashes above.

## 5. Verified tests

| Test | Result | Commit | Where it ran |
|---|---|---|---|
| S-01 Linters (pytest rules, ruff, shellcheck, yamllint, actionlint) | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-02 Secret scan (gitleaks, full history) | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-03 Actions pinned by commit SHA | pass | `384c2e3` | GitHub Actions run 43458827403 |
| S-04 State file and ADR index | pass | `384c2e3` | GitHub Actions run 43458827403 |

| B-01 Image construction (build exits 0, `bootc container lint --fatal-warnings`, label `containers.bootc=1`), both variants | pass | `399d421` | GitHub Actions run 43460695621 |
| B-08 Disk image (GPT, EFI system partition, btrfs root), checked from inside the VM; raw image, not qcow2 | pass | `399d421` | GitHub Actions run 43460695621 |
| V-01 Boot: SSH reachable, system state `running`, no failed units | pass | `399d421` | GitHub Actions run 43460695621, KVM |
| V-02 Shutdown: QEMU exit 0 after `poweroff`, kernel "Power down" on serial, clean second boot, `/etc` and `/var` sentinels kept | pass | `399d421` | GitHub Actions run 43460695621, KVM |

Early signals that also passed in run 43460695621 (they do **not** replace the full
tests): the booted system is the image built from the tested commit; SELinux reports
Enforcing (part of V-08); `/usr` is read-only (part of V-06).

Measurements from run 43461672095 (`a3a5004`; 2 vCPU, 4 GiB, KVM on a hosted runner).
These are observations, not the V-12 baseline, which is task P1-17:

| Metric | First boot | Second boot |
|---|---|---|
| Startup (kernel + initrd + userspace) | 11.7 s (1.1 + 3.8 + 6.8) | 7.9 s (1.1 + 2.8 + 4.0) |
| Memory in use (`free -m`, "used") | 462 MiB | 436 MiB |
| Failed units | 0 | 0 |
| SELinux denials logged | 3 | 3 |

Memory in use is above the blueprint's provisional 400 MiB budget for V-12; the image is
still the unmodified Fedora service set, so this is expected to change in P1-08.

| B-02 Package manifest (names, 540 packages), both variants | pass | `5d839d4` | GitHub Actions run 43547501384 |
| B-03 Enabled and masked units, both variants | pass | `5d839d4` | GitHub Actions run 43547501384 |
| B-04 Setuid/setgid files and file capabilities, both variants | pass | `5d839d4` | GitHub Actions run 43547501384 |
| Golden manifests detect unlisted content (negative check) | pass | `58a46d0` | run 43546633024 failed for exactly the four manifests that were still empty |
| Release variant boots to a console login prompt with no failed unit and powers off on the ACPI power button (V-01/V-02 for `aegis-base`, console only) | pass | `5d839d4` | GitHub Actions run 43547501384, KVM |

| V-17 Accounts: root locked, no account with a usable or empty password, no regular users; dev SSH server offers public-key login only | pass | `bf592c8` | GitHub Actions run 43550888887, KVM |
| V-20 Automatic update timer is masked and not scheduled | pass | `bf592c8` | GitHub Actions run 43550888887, KVM |
| Service baseline: every unit the preset turns off is inactive and disabled at runtime | pass | `bf592c8` | GitHub Actions run 43550888887, KVM |
| Identity: `os-release` and hostname say AEGIS in both variants; release variant answers nothing on the SSH port | pass | `bf592c8` | GitHub Actions run 43550888887, KVM |
| `/etc` changes equal the reviewed list (ADR-0014), both variants | pass | `bf592c8` | GitHub Actions run 43550888887 |

| V-03 Kernel: one kernel in the image and it is the one running; not tainted; only allow-listed error messages | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-10 Networking: address and route from DHCP; name resolution through systemd-resolved; outbound fetch by name; listeners equal the golden list (harness DNS and HTTP servers, no internet; HTTP not HTTPS) | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-11 Firewall: firewalld active, default zone `aegis` with target DROP, drop verdict in the kernel ruleset; a listener outside the zone is unreachable from outside, with positive controls | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| V-19 Kernel arguments, lockdown in integrity mode, 31 sysctl values equal the golden lists; reverse-path filtering never off | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |
| Audit daemon attached to the kernel, auditing enabled, log written | pass | `e378b1e` | GitHub Actions run 43554108533, KVM |

| V-08 SELinux: enforcing and not switchable off from the kernel command line; zero denials during boot (audit log and journal); install-time files carry the types `bootupd` may use; no `unlabeled_t` or `default_t` file; no service in `unconfined_service_t` or `initrc_t`; self-test domain may read what its policy allows and is refused what it does not, logged with `permissive=0` | pass | `c3308a8` | GitHub Actions run 43557838924, KVM (also run 43557821995) |
| Whole M2 suite on one commit: 14 image tests, 55 VM tests (includes the M1 tests B-01, B-08, V-01, V-02) | pass | `c3308a8` | GitHub Actions run 43557838924, KVM (also run 43557821995) |

| M2 suite repeated on the renewed base image (14 image tests, 55 VM tests) | pass | `aafc33a` | GitHub Actions run 43719668136, KVM |
| Local VM image: exported QCOW2 started with the published Linux launcher; console autologin, SSH, health, SELinux enforcing, power-off, unchanged checksum (7 tests) | pass | `aafc33a` | GitHub Actions run 43719668136, KVM |
| Local VM image: published artifact started with the PowerShell launcher; checksums, console autologin, SSH, SELinux enforcing, power-off | pass | `aafc33a` | GitHub Actions run 43719668136, job `windows-launch`, Windows Server 2025, software emulation |

### M3 tests (sealed boot chain)

All in GitHub Actions run 44300954850 on `3a07962` (first passed in run 44100054742 on
`21bb955`), KVM, OVMF Secure Boot firmware with only that run's throw-away keys
enrolled (`virt-fw-vars`). `lint` run 44300954927 green on the same commit.

| Test | Result | Evidence |
|---|---|---|
| B-06 Sealed structure, both variants: one UKI, no kernel outside it, no bootupd, composefs backend selected; UKI and boot loader verify against the db certificate and not against an unrelated one; UKI command line carries the image's storage digest (no `?`) and every golden argument | pass | `tests/image/test_sealed.py` |
| V-04 Secure Boot: `SecureBoot`=1, `SetupMode`=0, `bootctl`: "enabled (user)"; kernel "Secure boot enabled", lockdown `[integrity]`; booted by systemd-boot then systemd-stub | pass | `tests/vm/test_secure_boot.py` |
| V-06 Sealed root: `/proc/cmdline` equals the signed command line; `/` is a read-only composefs overlay of the deployed digest; the stored object of a root file has the fs-verity flag; `/usr` not writable | pass | as above. The write attempt on the object failed with "Read-only file system" (the physical root is read-only at runtime); it does not by itself demonstrate fs-verity |
| `/etc` (per deployment) and `/var` (`/state/os/default/var`) are writable state outside the sealed root | pass | as above |
| V-05 Unsigned UKI rejected (systemd-boot: "Error loading") | pass | `tests/vm/test_integrity.py` |
| V-05 UKI with one byte of its signed command line changed (`audit=1`→`audit=0`) rejected ("Error loading") | pass | as above |
| V-05 Unsigned boot loader rejected (firmware: "Access Denied -- rejected probably by Secure Boot") | pass | as above |
| Control: the unchanged disk boots with the same firmware and keys | pass | as above |
| V-07 64 bytes of the live object of a sealed root file inverted on the disk (offset located with filefrag and btrfs-map-logical): reading the file fails with "Input/output error", the content is never served | pass | as above. Which layer refused the data (btrfs checksums or fs-verity) was not logged; both would |
| Boot-entry `options enforcing=0 aegis.tamper=1` added on the ESP: ignored, SELinux enforcing | pass | as above |
| `io.systemd.stub.kernel-cmdline-extra=enforcing=0` in SMBIOS: the machine powers itself off before `sysinit.target` with "unexpected argument: enforcing=0" | pass (after the fix; failed in run 44093307831) | as above |
| All M1/M2 tests on the sealed images under Secure Boot, including clean power-off of both variants | pass | 77 of 77; BUG-8 fixed |

### Measurements after M3

`aegis-dev`, first boot, run 44300954850 (`3a07962`), same runner type as M2. Startup
time is measured by systemd and excludes firmware and boot loader.

| Metric | M2 (run 43557838924) | M3 |
|---|---|---|
| Startup, first boot | 9.3 s | 9.2 s (1.0 + 2.6 + 5.5) |
| Startup, second boot | 7.4 s | 7.7 s |
| Memory in use | 509–529 MiB | 498 MiB |
| Running services | 22 | 22 |
| Enabled units | 58 | 57 |
| TCP/UDP listeners | 8 | 8 |
| SELinux denials | 0 | 0 |
| Exported QCOW2 | 1.15 GiB | 1.5 GiB |
| `build` workflow duration | 17 min | 11 min (run 44300954850; 15 more tests, 7 extra boots; runner variation is large) |

Single runs on shared runners; differences under a second are not significant. The
image is about 0.35 GiB larger: the UKI (135 MB, kernel and initramfs) on the ESP and
the composefs object store.

| V-13 Signed update staged and booted under Secure Boot | pass | `a7cd392` | GitHub Actions run 44319072870, KVM |
| V-14 Rollback to v1 under Secure Boot | pass | `a7cd392` | GitHub Actions run 44319072870, KVM |
| V-15 Unsigned and untrusted-signed updates refused by the signature policy, nothing staged | pass | `a7cd392` | GitHub Actions run 44319072870, KVM |
| V-09 `/etc` and `/var` state survives update and rollback | pass | `a7cd392` | GitHub Actions run 44319072870, KVM |

| R-01 Input determinism: two builds, identical base, lock, RPM files, builder inputs, installed package sets | pass | `cd9bf7c` | GitHub Actions run 44738357964 |
| R-02 Content determinism: identical composefs digests of aegis-base and aegis-dev from two independent clean builds | pass | `cd9bf7c` | GitHub Actions run 44738357964 |
| R-03 OCI digest equality | reported: not equal (one layer per image differs) | `cd9bf7c` | GitHub Actions run 44738357964 |
| B-07 SBOM: valid SPDX 2.3, same packages and count as B-02, locked versions installed | pass (SBOM part; `cosign verify` not run) | `cd9bf7c` | GitHub Actions run 44738357964 |
| Locked inputs: size, SHA-256, header, Fedora signature of 75 RPMs; 8 negative cases refused | pass | `cd9bf7c` | GitHub Actions run 44738357964 |
| M1 to M4 suites (Secure Boot, SELinux, sealed root, signed update, untrusted and unsigned update refused, rollback) on locked inputs | pass (83 VM tests) | `cd9bf7c` | GitHub Actions run 44738357964, KVM |

Not yet run: B-05, the `cosign verify` part of B-07, V-12, V-16, V-18.

### Measurements before and after M2

`aegis-dev`, first boot unless stated, 2 vCPU, 4 GiB, KVM on a hosted runner. Before:
stock Fedora service set, run 43546633024 (`58a46d0`). After: M2 baseline, run
43557838924 (`c3308a8`); run 43557821995 gave 9.3 s, 7.4 s and 529 MiB. Single runs on shared runners; differences of a few tenths of
a second or a few MiB are noise. These are observations, not the V-12 baseline (P1-17).

| Metric | Before | After |
|---|---|---|
| Startup, first boot | 8.9 s (0.9 kernel + 2.6 initrd + 5.4 userspace) | 9.3 s (0.9 + 2.6 + 5.8) |
| Startup, second boot | 7.1 s | 7.1 s |
| Memory in use (MemTotal - MemAvailable) | 472 MiB | 509 MiB |
| Running services | 22 | 22 |
| Enabled units | 63 | 58 |
| Active timers | 6 | 4 |
| TCP/UDP listeners | 14 (sshd, LLMNR 5355 and mDNS 5353 on all interfaces; DNS stub and chrony on loopback) | 8 (sshd on all interfaces, development variant only; DNS stub and chrony on loopback) |
| Processes | 153 | 150 |
| Failed units | 0 | 0 |
| SELinux denials per boot | 3 (BUG-1) | 0 |
| SELinux permissive domains in the policy | 31 | 31 |
| Setuid/setgid files, files with capabilities | 17, 8 | 17, 8 |

The baseline is not lighter than stock Fedora: firewalld and auditd were added, and
they cost about 40 to 60 MiB and up to 0.4 s of startup. The number of running services is
the same because two were added and two (avahi, sssd-related) removed. Memory in use is
above the blueprint's provisional 400 MiB budget for V-12; that budget is revisited in
P1-17.

Nothing has been verified on a local workstation or on physical hardware.

## 6. Known bugs

| ID | Description | Impact | Plan |
|---|---|---|---|
| BUG-1 | Closed for disks built by this repository (`c3308a8`, run 43557838924: zero denials). Every boot logged 3 SELinux denials: `bootloader-update.service` runs `bootupctl` (domain `bootupd_t`, declared permissive by Fedora), which reads `/sysroot/.bootc-aleph.json` and files under `/sysroot/boot`. 344 files written at the end of the installation (the whole `/boot/grub2` tree, `/boot/bootupd-state.json`, `/.bootc-aleph.json`) carried the catch-all type `default_t`. Cause: on an SELinux system they inherit `boot_t` and `root_t` from their directories, which is what Fedora's policy lets `bootupd_t` use; our disks are installed on a GitHub runner whose kernel has no SELinux, so nothing is inherited. Supported by the result (giving them the parents' labels removes every denial), not by a comparison install on an SELinux host. A first attempt with file-context rules in a policy module had no effect (run 43554934333) and was removed. | None left in our disks. A disk installed by other means on a host without SELinux would still log the denials (nothing is blocked; the domain is permissive). | `scripts/fix-install-labels`, run by `scripts/build-disk` after the installation, gives every `default_t` file outside the ostree repository the label of its parent directory. No policy change. An installer that runs on an SELinux system (Phase 6) should not need it. Worth reporting to bootc upstream (owner's decision; text can be prepared). |
| BUG-2 | Closed (`bf592c8`). The image identified itself as Fedora; `os-release` and the hostname now say AEGIS. The initramfs part remains as BUG-5. | | |
| BUG-3 | At power-off the console shows "Failed to unmount /run/shutdown/mounts/...: Device or resource busy" and "Not all file systems unmounted, 1 left" before "Syncing filesystems" and "Power down". Seen on `aegis-base` in run 43546633024. | None observed: the following boot shows no filesystem recovery (V-02). Looks like the physical root that backs the running deployment. | Confirm the cause; re-check after the sealed boot chain changes the mount layout (P1-11). |
| BUG-4 | Closed. `podman build` 4.9 left an empty `/etc/hostname` in the image; the image now ships that file with the static hostname `aegis`. | | |
| BUG-6 | `ausearch -ts boot` returns nothing on the test VM although the audit log is being written (run 43554108533). | Tests that query the audit log by "since boot" would silently see no events. | The SELinux tests read the whole audit log and the journal and filter by time themselves. Cause not yet investigated. |
| BUG-5 | The initramfs is the one built by Fedora. It contains Fedora's `os-release`, so early boot identifies itself as Fedora and sets the hostname `fedora` until the real system applies `/etc/hostname`. | Cosmetic in M2. | The initramfs is regenerated when the UKI is built for the sealed boot chain (P1-11). |
| BUG-7 | Closed (`mirror-base` run 43851534053). The base image pin did not last: quay.io dropped the digests of 2026-11-13 and 2026-11-15 within one to two days; the repository has only moving tags. | Commits before the mirror cannot be rebuilt from their own pin (table in `docs/operations/base-image.md`). | Every pinned base is now copied, digest unchanged, to `ghcr.io/ben10-games/aegis-os/fedora-bootc`, and builds use the copy. Added packages are still unlocked (P1-15). |
| BUG-8 | Closed (`ec285da`, verified in run 44300954850). `/var` could not be unmounted at shutdown ("target is busy"). Cause, shown by shutdown diagnostics (run 44298288483): journald kept `/var/log/journal` open. With the composefs backend `/var` is a bind mount made by the initramfs, so `var.mount` has no unit file; for such a mount systemd turns `RequiresMountsFor=` into ordering only, so stopping `var.mount` never stopped `systemd-journal-flush.service` and its `journalctl --smart-relinquish-var` never ran. (On the ostree backend a generator writes a `var.mount` unit file.) | The release-variant power-off test failed; data was synced and later boots were clean. | `aegis-journal-relinquish.service` requires `var.mount` and conflicts with `shutdown.target`, so `journalctl --relinquish-var` runs right before `/var` is unmounted; `var.mount` is ordered before `local-fs.target`. The shutdown diagnostic shows no process holding `/var` at that point. |
| BUG-9 | Closed by mitigation. systemd-stub appends `io.systemd.stub.kernel-cmdline-extra` from SMBIOS even under Secure Boot; `enforcing=0` there made SELinux permissive (run 44093307831). | Whoever controls the firmware tables could weaken the system. | `aegis-verify-cmdline.service` powers the machine off on any argument not in the sealed set (verified in run 44096629031). The initramfs still runs before the check. |

## 7. Security limitations

`docs/architecture/security-baseline.md` lists what the image provides after M4, with the test
for each statement, and what it does not. In short:

- The boot chain is verified only in virtual machines with the build's throw-away keys.
  Keys for real hardware (own keys or shim) are an open decision (ADR-0012). The keys
  change with every CI run, so images from different runs need different firmware
  variables.
- `/etc` and `/var` are writable state outside the sealed root and not
  integrity-protected; a program that gains root can persist there. The ESP and the
  UKI are protected only by Secure Boot signatures; the disk is not encrypted.
- The initramfs runs before `aegis-verify-cmdline.service`, so a firmware-supplied
  kernel argument is in effect until that check stops the machine (BUG-9). Measured
  boot with a TPM policy is not implemented.
- Signed updates and manual rollback work (M4), but the signing key is generated per CI
  run: an installed image accepts updates only from the run that built it. There is no
  update channel and no automatic boot counting or rollback (Phase 2).
- `/etc/containers/policy.json`, which decides which updates are accepted, is in `/etc`
  (writable state); root can replace it. The public key itself is in the sealed root.
- Published images in GHCR are signed but the package is private by default; signatures
  are verifiable only with the public key of the run that published them.
- The local VM launchers boot the sealed image with plain firmware, without Secure Boot:
  fs-verity still checks the root, but nothing verifies the UKI (`LOCAL_VM_GUIDE.md`).
- 31 SELinux domains are permissive in Fedora's policy
  (`tests/golden/base/selinux-permissive-domains.txt`); programs in them are logged, not
  confined. `bootupd_t` is the one that runs at every boot. Root can switch SELinux to
  permissive at runtime.
- Root access can be granted from outside the image through systemd credentials in the
  firmware's SMBIOS strings (an SSH key, or unit files and drop-ins that run as root).
  This is how the test harness and the local VM launchers log in and is equivalent to
  console access; whether a release image should honour them is a Phase 2 decision.
- Reverse-path filtering is strict on every interface except the one that carries the
  default route, which is loose. Shown by experiment in run 43554108533: after forcing
  the value to strict, `nmcli device reapply` set it back to loose. NetworkManager
  relaxes it on purpose for interfaces with a default route. Filtering is never off.
- The release variant (`aegis-base`) is tested from outside only (console output, power
  button, closed SSH port, image manifests). Runtime checks that need a shell run on the
  development variant, which differs by the recorded delta (sshd and the SELinux
  self-test).
- The SELinux label correction (BUG-1) applies to disks built by this repository.
- The disk is created by `bootc install to-disk --generic-image` with bootc's default
  partition layout (recorded in M2 as a BIOS boot partition and a 512 MiB ESP; not
  re-measured since the composefs backend replaced ostree in M3). A fixed layout
  (`build/disk/phase1.toml`) is not implemented.
- Package goldens hold names; versions are pinned by the RPM lock and checked against
  the SBOM (`test_locked_packages_are_installed_in_the_locked_version`). The base image's
  own packages are pinned by its digest only.
- R-02 is shown for two builds on one runner on one day, with the same throw-away keys
  (they are build inputs). Builds on different days may differ where software records
  the date (for example password-ageing fields if a package creates a user); not tested.
- The vulnerability scan is a report. grype has no Fedora RPM data; Fedora advisories are
  read from Fedora's update metadata at scan time. Nothing acts on findings yet.
- The RPM cache and base image live only in GHCR; losing them makes old commits
  unbuildable (no retention policy yet).
- Planned Phase 1 limitations (see blueprint section 11): no disk encryption, throw-away
  signing keys, no automatic rollback on failed boot, no application sandboxing, `/etc`
  and `/var` are not integrity-protected.
- Nothing has been tested on physical hardware.

## 8. Assumptions

| ID | Assumption | State |
|---|---|---|
| A1 | GitHub-hosted Linux runners expose usable KVM | **confirmed** (QEMU started with `-accel kvm`, probe run 43459049502) |
| A2 | `fedora-bootc:45` ships bootc 1.16 or newer | **confirmed** (bootc 1.17.1, probe run 43459049502) |
| A3 | `bootc install to-disk` supports btrfs with the composefs backend | **confirmed** for both backends: ostree (run 43460695621) and composefs (B-08 asserts a btrfs root; passed in runs 44300954850 and 44319072870) |
| A4 | Fedora's updates-archive repository is usable for locked RPMs | not needed: locked RPMs are kept in an immutable GHCR image (ADR-0006); not tested |
| A5 | Container signature policy is enforced on the composefs backend | **confirmed** (run 44319072870, V-15: unsigned and wrongly signed images refused by the policy) |
| A6 | SSH key injection through a systemd credential on the QEMU command line works | **confirmed** (run 43460695621) |

## 9. Outstanding tasks and open decisions for the owner

Open decisions:

- Base image mirror: implemented as directed (M3 precondition). The package
  `aegis-os/fedora-bootc` is private by default; making it public in its settings on
  GitHub lets anyone build from a clone without logging in.
- Whether the `windows-launch` job may install QEMU from the Chocolatey community
  repository on the hosted Windows runner (test only).

- Repository licence.
- Whether the repository is public (affects CI minutes and package visibility).
- Whether a local Linux machine with KVM is available for interactive debugging.
- Whether to allow Fedora hosts in the Claude Cloud network policy later.

## 10. Environment notes

Claude Cloud, probed 2026-11-13:

- No `/dev/kvm`, no vmx/svm CPU flags.
- Docker client present, no daemon running; no podman, buildah, skopeo, QEMU.
- `quay.io`, `registry.fedoraproject.org` and Fedora mirrors are blocked by network policy.
- `ghcr.io`, `github.com`, `pypi.org`, `registry-1.docker.io` are reachable.
- Installing additional tools (pip, go install) was refused by the session's permission
  policy, so only `python3`, `pytest`, `ruff`, `make` and `git` are available. shellcheck,
  yamllint, actionlint and gitleaks therefore run only in CI.

GitHub Actions hosted runner (`ubuntu-24.04`), probed 2026-11-13, run 43459049502:

- 4 CPUs, 15.6 GiB RAM, 83 GiB free disk, kernel 7.0.0-azure.
- `/dev/kvm` present; usable by the runner user after a udev rule; QEMU 8.2.2 (apt) starts
  with KVM acceleration.
- Loop devices can be attached inside a privileged podman container.
- podman 4.9.3, buildah 1.33.7, skopeo 1.13.3, Docker 28.0.4 (daemon running).
- quay.io, registry.fedoraproject.org, Fedora mirrors, ghcr.io all reachable.

`quay.io/fedora/fedora-bootc:45` on 2026-11-15 is
`sha256:17227a17c0bb9222918881e27f254e219eb3808ceb4399e26322bbd2e77932bc` (probe run
43717628014): same bootc, kernel, systemd, selinux-policy and openssh versions and the
same package count (540) as below.

`quay.io/fedora/fedora-bootc:45` on 2026-11-13
(`sha256:42259b1db41a7f792a19cfd28e0c66e3e415392109a7d7095f292ad1e2a56453`):

- bootc 1.17.1, kernel 7.3.3-300.fc45, systemd 262.1, selinux-policy-targeted 45.24,
  openssh-server 10.5p1, 540 packages.
- `bootupd` 0.3.2 is installed (must be removed for the sealed path, P1-11).
- Not installed: `systemd-boot-unsigned`, `systemd-ukify`, `firewalld`, `audit`.

GitHub quirk: a workflow with a `paths` filter did not start on the first push of a new
branch; it started on the next push that touched a matching path.

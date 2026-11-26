---
name: aegis-gui-architect
description: Use when deciding how an AEGIS OS desktop feature fits the architecture - KDE Plasma 6 on KWin (Wayland), Qt 6/QML, Kirigami, where configuration lives, what may run privileged, and whether Quickshell or another shell is appropriate. Read before adding packages, services or session components to the aegis-gui image.
---

# AEGIS GUI architect

The architecture is fixed in `docs/architecture/gui-architecture.md`. Read it first.

## Rules to apply to every proposal

1. **One shell.** plasmashell is the shell. Never run Quickshell, a second panel daemon or
   another layer-shell client as a competing shell in the same session.
2. **No own compositor.** KWin is the compositor. Extend it with KWin scripts or effects
   only when Plasma configuration cannot do the job.
3. **No GUI process runs as root.** System changes go through a polkit-authorised D-Bus
   service with its own SELinux domain; write a design note before writing the service.
4. **Configuration in `/usr`.** Look-and-feel, colour schemes, wallpapers, layouts and
   KConfig defaults go under `/usr/share` or `/usr/lib`; `/etc` only when the software
   reads nothing else (ADR-0014), and then list it.
5. **The boot chain is untouchable.** The GUI image is sealed by `scripts/seal-image`
   like every variant; do not add kernel arguments for the GUI.
6. **Wayland only.** No X11 session; XWayland only for applications that need it.

## Checklist for a new component

- Which existing Plasma/KDE piece already does it? Configure before you code.
- Process model: which process, which user, which SELinux domain?
- Data access: which files or D-Bus interfaces, read or write?
- Test: which assertion in `tests/vm/test_gui.py` proves it works?
- Cost: packages added (`dnf install --assumeno` in the probe), memory measured in CI.

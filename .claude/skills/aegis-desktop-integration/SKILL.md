---
name: aegis-desktop-integration
description: Use when connecting AEGIS OS desktop components to system services - networking, sound, power, notifications, Bluetooth, application launching, security state - through least-privilege interfaces that keep SELinux, D-Bus policy and polkit boundaries intact.
---

# AEGIS desktop integration

## Interfaces to use

| Need | Interface | Already in aegis-gui |
|---|---|---|
| Networking | NetworkManager D-Bus (plasma-nm) | yes |
| Sound | PipeWire / WirePlumber (plasma-pa) | yes |
| Display | KScreen / KWin output management | yes |
| Files, opening, screenshots | xdg-desktop-portal-kde | yes |
| Power | logind and UPower D-Bus (PowerDevil) | not yet |
| Notifications | org.freedesktop.Notifications (plasmashell) | yes |
| Bluetooth | BlueZ D-Bus (bluedevil) | not yet |
| Security state | read-only: `/sys/firmware/efi/efivars`, `/sys/fs/selinux/enforce`, `/sys/kernel/security/lockdown`; `bootc status --json` needs a dedicated read-only service | design needed |

## Rules

- The session user gets no new privileges. Anything that changes the system is a
  polkit action with `auth_admin` by default; document each action.
- A new system service ships its own SELinux module (compiled like
  `policy/selinux/aegis_selftest.te`), never `unconfined_service_t`, never permissive,
  never `dontaudit` (enforced by `tests/static/test_repo_hygiene.py`).
- D-Bus policy files go to `/usr/share/dbus-1/system.d/` and allow only the methods the
  UI needs.
- Prove it in the VM: the `gui` job fails on any SELinux denial in the session.

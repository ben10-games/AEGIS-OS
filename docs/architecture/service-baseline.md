# Service baseline

What AEGIS changes in the set of systemd units the Fedora bootc base enables, and why.
The enforced record is `tests/golden/base/enabled-units.txt` and
`tests/golden/base/masked-units.txt`; this file gives the reasons.

## Rule

A unit is turned off only if both hold:

1. Nothing that stays enabled depends on it. Checked on a running system with
   `systemctl list-dependencies --reverse` (build run 43547501384).
2. It opens a network or remote-access surface, performs unattended network activity, or
   serves a role AEGIS does not target in Phase 1.

Everything else stays as Fedora ships it. Removing packages is a separate decision
(ADR-0013); the one exception is the SSH server.

## Changes to the release image (`aegis-base`)

| Unit or package | Change | Reason | Dependency evidence |
|---|---|---|---|
| `openssh-server` (package) | removed | A release image carries no remote-login daemon (ADR-0002). Removal is stronger than disabling: there is no binary to start. | Wanted only by `multi-user.target` |
| `avahi-daemon.service`, `avahi-daemon.socket` | disabled | mDNS responder listening on UDP 5353 on every interface. Nothing in AEGIS uses it. | Wanted only by targets |
| `sssd.service` | disabled | Directory login (AD, IPA, LDAP). Not a Phase 1 target; it was enabled but inactive. | Wanted only by `multi-user.target` |
| `nfs-client.target` | disabled | Starts NFS client helpers at every boot. A user who mounts NFS can enable it. | Wanted by `multi-user.target` and `remote-fs.target` only |
| `rpm-ostree-countme.timer` | disabled | Weekly usage count sent to Fedora's mirrors: unattended network activity to a third party. | Wanted only by `timers.target` |
| `bootc-fetch-apply-updates.timer` | disabled and masked | Downloads and applies updates and reboots the machine without asking. Update policy is a Phase 2 design (V-20). | Wanted only by `timers.target` |
| `systemd-sysext.service`, `systemd-confext.service` | disabled | They overlay `/usr` and `/etc` at boot with extension images found under `/var` or `/etc`: content outside the verified OS image, and a way to persist. Off until there is a signature policy. | Wanted only by `sysinit.target`; inactive on a stock system |

## Added to the release image

| Unit | Reason |
|---|---|
| `firewalld.service` | Firewall manager (ADR-0008). The default zone `aegis` drops unsolicited incoming traffic and offers nothing to the network. |
| `auditd.service` | Records security events, including SELinux denials, in `/var/log/audit`, where they can be queried with `ausearch`. |

## Considered and left alone

| Unit | Why it stays |
|---|---|
| `NetworkManager-wait-online.service` | Already inactive unless a unit asks for `network-online.target`. Disabling it would save nothing at boot and would break units that legitimately wait for the network. |
| `bootloader-update.service` | Keeps shim and GRUB current on the GRUB boot path. It is the source of BUG-1, which is fixed by labelling, not by turning the update off. Goes away with `bootupd` on the sealed path (P1-11). |
| `systemd-homed.service` | Unused today, but encrypted per-user home directories are a candidate for Phase 2. Decide there. |
| `udisks2.service` | Needed by a desktop for removable media. |
| `lvm2-*`, `dm-event.socket`, `mdmonitor.service`, `raid-check.timer` | Storage support for disks a user may attach. No network surface. Candidates for Phase 5 with measurements. |
| `clevis-luks-askpass.path` | Belongs to the disk-encryption decision in Phase 2. |
| `irqbalance.service`, `systemd-oomd.service`, `fstrim.timer`, `logrotate.timer`, `chronyd.service` | Ordinary housekeeping. |
| `systemd-report-*.socket`, `systemd-sysupdate-notify-*.socket`, `systemd-journalctl-metrics.socket` | Local sockets new in systemd 262; no network surface. Not yet evaluated individually. |

## Development variant (`aegis-dev`)

Adds `openssh-server` and enables `sshd.service`, with password and keyboard-interactive
login switched off on the server's command line. The login key is injected when the
virtual machine starts. Nothing else differs; see `tests/golden/dev/*.delta.txt`.

## Measurements

Before (stock Fedora service set) and after (this baseline) are recorded in
`PROJECT_STATE.md` section 5, taken on the same CI runner type. In short: 5 fewer enabled
units, 2 fewer timers, 6 fewer listeners, zero SELinux denials; about 40 to 60 MiB more
memory in use and up to 0.4 s more startup time, both caused by firewalld and auditd.

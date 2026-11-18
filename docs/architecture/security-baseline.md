# Security baseline after milestones M2 and M3

What the AEGIS OS image demonstrably provides after M3 and the update tests of M4
(sealed boot chain; gate G1 passed), what it does not, and where each statement is tested. "Tested" means a test in this repository passed in
GitHub Actions on a KVM virtual machine; the run is recorded in `PROJECT_STATE.md`.
Nothing here has been checked on physical hardware.

## Provided and tested

| Property | How | Test |
|---|---|---|
| The operating-system tree cannot be changed at runtime | `/usr` is read-only (bootc, composefs backend since M3) | `test_usr_is_read_only` |
| Mandatory access control is on | SELinux enforcing, Fedora's targeted policy, unchanged in the release image | V-08 |
| The policy is really enforced, not just loaded | A confined test domain is refused an access its policy does not grant; the refusal is logged with `permissive=0` (development variant) | V-08 self-test |
| Nothing is denied during a normal boot | Zero AVC records between power-on and the end of boot | V-08 |
| No service runs outside a confined domain | No process in `unconfined_service_t` or `initrc_t` | V-08 |
| Nothing is offered to the network | Development image: sshd is the only listener that is not on loopback. Release image: the SSH server is not installed and nothing answers on its port. The release image's listeners cannot be listed from inside (there is no way in); it differs from the development image only by the recorded delta | V-10, golden listeners, B-02, `test_base_has_no_remote_login` |
| Unsolicited incoming traffic is dropped | firewalld, default zone `aegis`, target DROP; proven with a listener that is unreachable from outside | V-11 |
| No default credentials | root locked, no account with a usable or empty password, no regular users | V-17 |
| The kernel refuses modification from user space | `lockdown=integrity`; kexec, unprivileged eBPF and userfaultfd off; kernel pointers and log restricted; 31 sysctl values | V-19 |
| Kernel is the one shipped, untainted, no unexpected errors | | V-03 |
| No unattended updates or reboots | update timer masked | V-20 |
| No unattended traffic to third parties | usage counter and connectivity check off; mDNS and LLMNR off | service baseline tests, V-10 |
| Security events are recorded from the first process on | `audit=1`, auditd | `test_audit_daemon_is_running` |
| What is in the image is what was reviewed | packages, enabled and masked units, setuid files, file capabilities, permissive SELinux domains and `/etc` changes are compared with golden manifests | B-02, B-03, B-04 |
| The firmware runs only boot code signed with the project's key (M3) | UEFI Secure Boot with own PK/KEK/db; systemd-boot and the UKI are signed; an unsigned or modified UKI or boot loader is refused | V-04, V-05 (VM, throw-away keys) |
| The kernel command line is the signed one | It is inside the signed UKI; boot-entry options are ignored; any other argument (e.g. from firmware SMBIOS strings) makes the system power off | V-06, boot-parameter tests |
| The operating system tree is exactly the built image | composefs root whose digest is in the signed command line; stored objects carry fs-verity; offline changes to a file's stored bytes make reads fail, never return the changed content | B-06, V-06, V-07 |
| The sealed system shuts down cleanly | `/etc` and `/var` are released before unmounting; both variants power off without failed units | release-variant power-off test (BUG-8 fixed) |
| Only signed updates are accepted (M4) | `/etc/containers/policy.json` rejects everything by default; AEGIS images need a sigstore signature by the key sealed into `/usr/share/aegis/keys/`. Unsigned and wrongly signed images are refused, nothing is staged | V-15 |
| An update can be undone | `bootc rollback` returns to the previous sealed image; `/etc` and `/var` state is kept | V-13, V-14, V-09 |

## Not provided yet

| Gap | Consequence | Planned |
|---|---|---|
| Boot chain tested only in VMs with throw-away keys | Nothing is known yet about real firmware; keys for hardware are undecided | Phase 6 (ADR-0012) |
| No measured boot (TPM) | A firmware-supplied kernel argument is in effect during the initramfs until the command-line check stops the machine | Phase 2 |
| No disk encryption | Everything on the disk is readable by anyone who has it | Phase 2 |
| Update keys are per CI run | An image accepts updates only from the run that built it; there is no update channel yet | Phase 2 (key hierarchy) |
| `/etc` and `/var` are not integrity-protected | A program that gains root can persist there, including in `/etc/containers/policy.json`, which decides which updates are accepted | Phase 2 |
| Root can switch SELinux to permissive at runtime | Enforcement protects against confined programs, not against root | Phase 2 |
| 31 SELinux domains are permissive in Fedora's policy | Programs in those domains are logged, not confined. Listed in `tests/golden/base/selinux-permissive-domains.txt`; `bootupd_t` is the one that runs at every boot | Phase 2: confine or remove; `bootupd` goes with the sealed boot chain |
| No application sandboxing | Any program a user runs has that user's full access | Phase 3 |
| No audit rules beyond the defaults | Only events the kernel and systemd report are recorded | Phase 2 |
| No automatic rollback on a failed boot | A bad update needs a manual choice in the boot menu | Phase 2 |

## Decisions with a cost

- **Reverse-path filtering is loose on the interface with the default route.** The
  image sets strict filtering everywhere. NetworkManager changes it to loose on the
  interface that carries the default route; an experiment in CI showed the value going
  back to loose after `nmcli device reapply`. Filtering is never off: packets whose
  source address is unreachable through any interface are still dropped.
- **The firewall and audit daemons cost memory.** See the before/after table in
  `PROJECT_STATE.md`.
- **Root access can be granted from outside the image.** systemd reads credentials
  from the firmware's SMBIOS strings. Whoever configures the virtual machine can
  install an SSH key for root, and can add unit files and drop-ins, which run as root.
  This is how the test harness and the local test image log in (`LOCAL_VM_GUIDE.md`),
  and it is equivalent to physical access to the console. On physical hardware these
  strings are set by the manufacturer. A release image should decide deliberately
  whether to honour them (Phase 2).

## Findings that are not AEGIS defects but affect it

- **Installing from a host without SELinux leaves files mislabelled** (BUG-1). The
  bootloader files under `/boot/grub2`, `bootupd`'s state file and bootc's install
  record (344 files) carried the catch-all type `default_t`, which caused three denials
  at every boot. `scripts/fix-install-labels` gives them the label of their directory
  when this repository builds a disk. The policy is unchanged. A disk installed by
  other means on a host without SELinux would still have the problem.
- **`ausearch -ts boot` returns nothing** on the test system (BUG-6). The tests read
  the whole audit log and filter by time themselves.
- **The initramfs is Fedora's** (BUG-5), so early boot identifies itself as Fedora.

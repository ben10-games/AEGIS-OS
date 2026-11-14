# ADR-0014: Where AEGIS configuration lives

Status: Accepted
Date: 2026-11-14

## Context

The blueprint's rule was "AEGIS ships configuration under `/usr/lib` and writes nothing to `/etc`", so that `/etc` holds only local changes and drift can be seen. Some software reads only `/etc`: firewalld takes its default zone from `/etc/firewalld/firewalld.conf`, systemd records unit enablement and masks as symlinks under `/etc/systemd/system`, and the SELinux policy store is under `/etc/selinux`. Removing a package also removes its files from `/etc`.

## Decision

AEGIS configuration goes under `/usr/lib` whenever the software reads it there. Where it does not, the image may change `/etc`, and every file the image adds, modifies or deletes under `/etc`, compared with the pinned upstream base, is listed in `tests/golden/base/etc-changes.txt` (and `tests/golden/dev/etc-changes.delta.txt` for the development variant). CI compares the list with the built image.

The SELinux policy store (`/etc/selinux/targeted/**`) appears as one entry, because installing a policy module regenerates many files there; the policy itself is checked by the SELinux tests.

## Consequences

- The rule stays enforceable: an unreviewed change under `/etc` fails the build.
- The golden file is the reviewed list of everything AEGIS does to `/etc`.
- On an installed system, the difference between the image's `/etc` and the machine's `/etc` is still exactly the local configuration.

## Verification

`tests/image/test_manifests.py` (`etc-changes.txt`), run by `make image-test`.

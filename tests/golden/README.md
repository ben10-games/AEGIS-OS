# Golden manifests

These files are the reviewed record of what the AEGIS images contain. CI compares them
with the real images (`make inventory`, `make image-test`); any difference fails the build.

| File | Meaning | Test |
|---|---|---|
| `base/packages.txt` | Installed packages of `aegis-base`, as `name.arch` | B-02 |
| `base/enabled-units.txt`, `base/masked-units.txt` | systemd units enabled or masked in the image | B-03 |
| `base/setuid-files.txt`, `base/file-capabilities.txt` | Files that run with elevated privilege | B-04 |
| `base/selinux-permissive-domains.txt` | SELinux domains the policy does not enforce | V-08 |
| `base/etc-changes.txt` | Files AEGIS adds (A), modifies (M) or deletes (D) under `/etc` compared with the pinned upstream base | ADR-0014 |
| `dev/*.delta.txt` | What `aegis-dev` adds (`+`) or removes (`-`) relative to `aegis-base` | same tests |

Three more files are compared with a running system, not with the image inventory:

| File | Meaning | Test |
|---|---|---|
| `kargs.txt` | Kernel arguments AEGIS adds | V-19 |
| `sysctl.txt` | Kernel settings and their values | V-19 |
| `kernel-error-allowlist.txt` | Error-level kernel messages that are expected | V-03 |
| `listening-sockets-dev.txt` | TCP and UDP listeners of a running `aegis-dev` | V-10 |

One entry per line. Lines starting with `#` and empty lines are ignored.

Package entries carry no version: packages AEGIS adds are not version-locked until the
RPM lockfile exists (task P1-15). The base image itself is pinned by digest.

## Changing them

A golden file changes only together with the image change that causes it, in the same
commit, so the effect of the change is visible in review. On a machine that can build:

```bash
make image builder inventory golden-update
```

From a cloud session, copy the lists from the "Collect results" step of the `build` job.

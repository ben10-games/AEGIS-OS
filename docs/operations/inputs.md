# Build inputs: the RPM lock and how to update it

Every package AEGIS adds to the base image comes from one reviewed file,
`image/packages/rpms.lock.yaml` (task P1-15, ADR-0006). The base image itself is pinned
in `image/base.lock` (`docs/operations/base-image.md`).

## What is locked

| File | Content |
|---|---|
| `image/packages/rpms.in.yaml` | What each install step adds: `base`, `dev`, `dev-policy`, `builder`. Names only. |
| `image/packages/rpms.lock.yaml` | Generated. Every package each step installs, dependencies included: name, epoch, version, release, arch, size, SHA-256, Fedora repository and path. Header: base image digest, SHA-256 of `rpms.in.yaml`, resolution time, and the digest of the RPM cache image. |
| `ghcr.io/ben10-games/aegis-os/rpm-inputs@sha256:…` | The locked RPM files themselves, as an image (`/rpms/<step>/*.rpm`). Tag `lock-<hash of the package list>`; tags are never overwritten. |

## What every build checks (fail closed)

`scripts/fetch-inputs` (`make inputs`) runs before any image or builder build:

1. The lock matches `rpms.in.yaml` and `image/base.lock` (otherwise: "stale").
2. The cache image is pulled by its digest (otherwise: "could not be pulled").
3. The directory holds exactly the locked files: none missing, none extra, no links.
4. Each file has the locked size and SHA-256.
5. Each RPM header names the locked package (name, epoch, version, release, arch).
6. Each RPM carries a valid signature by the Fedora release key shipped in the base
   image (`rpmkeys --checksig` must say `digests signatures OK`; an unsigned package
   says `digests OK` and is refused).

The builds then run with `--network=none` and with every dnf repository disabled.
`image/build/install-locked` checks the SHA-256 sums again inside the build and installs
exactly that step's files; dnf fails if a dependency is missing. Nothing can come from
a mirror or be newer than the lock.

The negative tests (`make input-test`, `scripts/test-inputs`) run in every CI build on
real RPMs: a changed byte, a changed byte with a matching forged lock entry (caught by
the signature), a missing RPM, an extra RPM, a different genuine Fedora package under a
locked name with a forged lock entry (caught by the header check), a stale lock, an
unavailable cache image, and an offline install with one dependency removed.
`tests/static/test_rpm_lock.py` covers the parser and checks without RPMs.

## Updating the inputs

1. Change `rpms.in.yaml` (or the base pin), or start the `update-inputs` workflow by
   hand to pick up Fedora updates for the same names. The weekly scheduled run only
   reports what would change and publishes nothing.
2. The workflow resolves the names on the pinned base, downloads and verifies the
   RPMs, publishes them as a new cache image, fetches that image back by digest and
   verifies it as a build would, runs the negative tests, and prints the candidate lock
   between `BEGIN CANDIDATE LOCK` and `END CANDIDATE LOCK`, after a one-line-per-package
   summary of the changes. The candidate is also an artifact of the run.
3. Review the changes: every added or changed package, its repository, and that the
   requested names are still there. A package that appears without being requested is
   a new dependency; find out why.
4. Commit the candidate as `image/packages/rpms.lock.yaml`, together with any golden
   manifest changes the new packages cause (`tests/golden/`, CLAUDE.md rule 8).
5. The `build` workflow then runs every test on that commit. Only a green run makes the
   update usable.

Nothing in this process writes to the repository automatically, and the workflow's
registry token can only publish to this repository's packages.

## When it fails

| Message | Meaning | Action |
|---|---|---|
| `rpms.lock.yaml is stale` | `rpms.in.yaml` changed after the lock was generated | run `update-inputs`, review, commit the candidate |
| `resolved on …, but image/base.lock pins …` | the base pin changed | the same; resolution depends on the base |
| `could not be pulled` | the cache image is gone or the registry is unreachable | check the registry; never edit the digest by hand |
| `SHA-256 differs`, `size …`, `header says …`, `signature check: …` | an RPM is not the locked one | treat as a supply-chain incident; do not re-publish over it |
| `locked but missing`, `not in the lock` | the cache image does not match the lock | the same |

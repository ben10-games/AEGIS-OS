# The base image: pin, mirror, update, retention

AEGIS OS is built from one upstream image, `quay.io/fedora/fedora-bootc:45`. This
document says how that input is kept under control.

## Why a mirror

The upstream repository has only moving tags (`45`, `45-x86_64`, ...), and quay.io stops
serving a digest a day or two after the tag moves on. A digest pin alone therefore
breaks every build within days and makes old commits impossible to rebuild (BUG-7 in
`PROJECT_STATE.md`). The project keeps its own copy of every image it pins.

## How it works

`image/base.lock` records:

| Field | Meaning |
|---|---|
| `UPSTREAM_REPOSITORY`, `UPSTREAM_TAG` | where the image comes from |
| `UPSTREAM_DIGEST` | the digest the tag pointed to when it was resolved |
| `UPSTREAM_RESOLVED` | the date of that resolution |
| `MIRROR_REPOSITORY` | the project's copy, `ghcr.io/ben10-games/aegis-os/fedora-bootc` |
| `BASE_IMAGE` | what builds use: the mirror, addressed by the upstream digest |

The workflow `mirror-base` (`scripts/mirror-base`) copies the image for all
architectures with `skopeo copy --all --preserve-digests`. The copy therefore has
**the same digest as upstream**: the pin can be compared with quay.io for as long as
quay.io still serves it, and a static test requires `BASE_IMAGE` to carry
`UPSTREAM_DIGEST`. Each copy also gets a tag that is never moved,
`<tag>.<date>-<first 12 digits of the digest>`.

Safeguards:

- `mirror-base` is the only job in the repository with `packages: write`; a static test
  enforces this. All other workflows read.
- The job refuses to overwrite a tag that points to a different digest, and contains
  no delete operation.
- The registry token is GitHub's short-lived job token. It is passed through the
  environment and standard input, never written to the repository or printed.
- The job runs on a manual start or when `image/base.lock` changes. It never runs on
  pull requests.

## Provenance: what is and is not checked

- The image is fetched over TLS from Fedora's namespace on quay.io, by digest.
- The mirror job prints the image's creation time, its labels and the per-architecture
  manifests, and whether a sigstore signature object exists upstream.
- **Not done yet:** cryptographic verification of a Fedora signature on the image, and
  verification of the RPM signatures inside it. Both belong to task P1-13 (signing and
  signature policy). Until then, trust in the base rests on the transport and on the
  digest staying fixed.

## Updating the base (a reviewed change)

1. Run the `probe` workflow; it prints the digest the tag points to ("A2 base digest").
2. In `image/base.lock`, set `UPSTREAM_DIGEST` and `UPSTREAM_RESOLVED`, add a line to
   the history, and set `BASE_IMAGE` to the mirror with the new digest.
3. Push. `mirror-base` copies the image. The `build` run started by the same push may
   fail if it starts before the copy is complete; re-run it afterwards.
4. The golden manifest tests show what changed in the package set. Update
   `tests/golden/` in the same commit series (rule 8 in `CLAUDE.md`).

Do this promptly after resolving a digest: once upstream has dropped it, it cannot be
mirrored any more.

## Retention

- Never delete a mirrored image that any commit on a kept branch pins. Deleting it
  makes those commits impossible to rebuild.
- Nothing is deleted automatically. Deletion is a manual, deliberate action by the
  repository owner in the package settings on GitHub.
- Each copy is roughly the size of four architectures of the base image. If storage
  ever has to be reclaimed, remove the oldest copies first and record in
  `PROJECT_STATE.md` which commits can no longer be rebuilt.

## Which commits can be rebuilt

| Commits | Base pin | Rebuildable |
|---|---|---|
| up to `7529947` | digest of 2026-11-13, quay.io only | no: upstream dropped the digest |
| `0b3da6c` to the first commit that uses the mirror | digest of 2026-11-15, quay.io | only while quay.io serves it; yes after that by setting `BASE_IMAGE` to the mirror, which has the same digest |
| later commits | mirror | yes |

Rebuilding reproduces the base and the build recipe. Packages added by `dnf install`
during the build are not version-locked until task P1-15, so a rebuild can still
differ in those.

## Access

A package created by a workflow is private at first and readable by this repository's
workflows. To let anyone build from a clone, the owner can make the package public in
its settings on GitHub; the repository itself is public. Until then, a local build
needs `podman login ghcr.io` with a token that may read packages.

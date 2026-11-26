# ADR-0015: Persistent development signing identity for v3

Status: Accepted
Date: 2026-11-26

## Context

ADR-0007 made every Secure Boot and image signing key a throw-away key of one CI run.
AEGIS OS v3 ships a persistent VirtualBox disk that must accept system updates built by
later runs, so the key that signs an update and the key sealed into the installed image
must be the same across builds. The owner approved persistent **development** keys on
2026-11-26, provided they are created and stored only through a protected GitHub
Actions environment with restricted publishing permissions, and never appear in source
control, images, logs or artifacts. Production keys and production trust roots need a
separate approval.

## Decision

- One development identity: Secure Boot PK, KEK and db (RSA 2048, two-year
  certificates labelled "persistent development key, not for production") and one
  sigstore image signing key with a random passphrase.
- It is created once by the manually started workflow `dev-signing-bootstrap`, on the
  v3 branch only, in the environment `aegis-dev-bootstrap`, which requires the owner's
  approval and holds the owner's short-lived bootstrap token (repository secrets
  write, this repository only, revoked after use).
- The keys are generated on a tmpfs, sent to `gh secret set` on standard input and
  stored only as secrets of the environment `aegis-dev-signing`, whose deployments are
  limited to the v3 branch. Existing secrets are never replaced.
- Builds that use the identity run in `aegis-dev-signing`; every other build keeps
  throw-away keys (ADR-0007 still applies to them).
- Only public halves leave the environment: they are printed by the bootstrap job,
  committed under `keys/dev/` and compared with every image.
- No production key exists. Images signed with this identity are development images
  and are labelled experimental.

## Consequences

- An installed v3 disk can be updated by images from later runs (M9), and the
  cross-build tests can run under Secure Boot with the same enrolled keys.
- Anyone who can push to the v3 branch can have a build sign with the development key;
  the branch is therefore a development channel, not a trust root for production.
- Rotation: new environment secrets after deleting the old ones, a new `keys/dev/`
  commit, and a documented update path; old disks stop accepting updates signed only
  with the new key.

## Verification

Static tests: the bootstrap workflow is manual, branch-limited, in the reviewer-gated
environment and refuses to replace secrets; no private key under `keys/`; images carry
the committed public key (M9). CI: cross-build update test (M9).

# Setting up the development signing identity (owner steps)

ADR-0015. The keys are created inside GitHub Actions and stored only as GitHub
environment secrets. You never see, download or paste a private key. Production keys
are not part of this procedure.

What you do: create two environments and one short-lived token, start one workflow, then
delete the token. About 10 minutes.

## 1. Environment `aegis-dev-signing` (holds the keys)

GitHub → repository **AEGIS-OS** → **Settings** → **Environments** → **New environment**.

1. Name: `aegis-dev-signing` → **Configure environment**.
2. **Deployment branches and tags** → **Selected branches and tags** → **Add deployment
   branch or tag rule** → Ref type *Branch*, pattern `claude/aegis-os-v3` → **Add rule**.
3. Leave **Required reviewers** off. Every push to the v3 branch builds and tests with
   these keys, so a reviewer would block each test run. The branch rule is what
   protects them.
4. Add no secrets here yourself. The workflow adds them.

## 2. Environment `aegis-dev-bootstrap` (holds the one-time token, needs your approval)

**It probably exists already, unprotected**: on 2026-11-27 run 46015720213 started the
bootstrap job by mistake, and GitHub creates an environment that a job names if it does
not exist yet. That run stopped at the missing token; no key was generated and nothing
was stored. If it is listed, open it; otherwise **New environment** → name
`aegis-dev-bootstrap` → **Configure environment**. Then:

1. **Required reviewers**: tick it and add yourself (`ben10-games`). Leave **Prevent
   self-review** unticked: you are the only reviewer.
2. **Deployment branches and tags** → **Selected branches and tags** → rule for branch
   `claude/aegis-os-v3`.

## 3. The bootstrap token (fine-grained, 7 days, one repository)

Your profile picture → **Settings** → **Developer settings** → **Personal access
tokens** → **Fine-grained tokens** → **Generate new token**.

| Field | Value |
|---|---|
| Token name | `aegis-dev-bootstrap` |
| Expiration | 7 days |
| Resource owner | `ben10-games` |
| Repository access | **Only select repositories** → `ben10-games/AEGIS-OS` |
| Repository permissions | **Secrets: Read and write** and **Environments: Read-only** (Metadata: Read-only is added automatically). Nothing else. |

**Generate token** and copy it. Then, without pasting it anywhere else (not into a chat,
a file or a terminal):

Repository **Settings** → **Environments** → `aegis-dev-bootstrap` → **Environment
secrets** → **Add environment secret** → Name `AEGIS_DEV_BOOTSTRAP_TOKEN`, Value: the
token → **Add secret**.

## 4. Create the identity

Tell Claude that steps 1–3 are done. GitHub shows **Run workflow** only for workflows on
the default branch, and this one is only on `claude/aegis-os-v3`, so Claude starts it
with a commit to that branch that changes `keys/dev/bootstrap-request` and whose subject
line begins with `[bootstrap-dev-signing]`. Nothing else starts it.

A first job, without any secret, checks that `aegis-dev-bootstrap` requires a reviewer
and that `aegis-dev-signing` is limited to selected branches; if not, it stops and the
key job is never created. The run then waits for you: GitHub → **Actions** → **dev-signing-bootstrap** → the
waiting run → **Review deployments** → tick `aegis-dev-bootstrap` → **Approve and
deploy**. Before generating anything it checks that `aegis-dev-signing` is limited to
selected branches and that `aegis-dev-bootstrap` requires a reviewer, and stops if not.
It takes about 10 minutes. The log ends with the public certificates and fingerprints,
which are safe to publish. No private key is printed.

## 5. Remove the token

1. **Developer settings** → **Fine-grained tokens** → `aegis-dev-bootstrap` → **Delete**.
2. **Environments** → `aegis-dev-bootstrap` → delete the secret
   `AEGIS_DEV_BOOTSTRAP_TOKEN`.

`aegis-dev-signing` then holds ten secrets named `AEGIS_DEV_*`. Leave them alone.

## If something fails

- **"already holds …"**: the identity exists. Nothing was changed.
- **HTTP 403 from `gh api` or `gh secret`**: the token lacks a permission (step 3). Edit
  it, then ask Claude to start the workflow again. Nothing was stored.
- **"must be limited to selected branches" / "must require a reviewer"**: finish steps 1
  or 2. Nothing was generated.
- **The job never starts**: the branch rule or the review is missing (steps 1–2).

## Rotation (only if a key may have leaked, or before the certificates expire)

1. Delete the ten `AEGIS_DEV_*` secrets of `aegis-dev-signing`.
2. Repeat steps 3–5.
3. Commit the new public keys under `keys/dev/`.
4. Installed development disks keep the old key and no longer accept updates. Replace
   them with a new disk.

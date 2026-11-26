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

**New environment** → name `aegis-dev-bootstrap` → **Configure environment**.

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
| Repository permissions | **Secrets: Read and write** (Metadata: Read-only is added automatically). Nothing else. |

**Generate token** and copy it. Then, without pasting it anywhere else (not into a chat,
a file or a terminal):

Repository **Settings** → **Environments** → `aegis-dev-bootstrap` → **Environment
secrets** → **Add environment secret** → Name `AEGIS_DEV_BOOTSTRAP_TOKEN`, Value: the
token → **Add secret**.

## 4. Create the identity

Repository → **Actions** → **dev-signing-bootstrap** → **Run workflow** → branch
`claude/aegis-os-v3`, confirmation `create the development signing identity` →
**Run workflow**. (Or tell Claude that steps 1–3 are done; Claude starts it.)

The run waits for you: open it → **Review deployments** → tick `aegis-dev-bootstrap` →
**Approve and deploy**. It takes about 10 minutes. The log ends with the public
certificates and fingerprints, which are safe to publish. No private key is printed.

## 5. Remove the token

1. **Developer settings** → **Fine-grained tokens** → `aegis-dev-bootstrap` → **Delete**.
2. **Environments** → `aegis-dev-bootstrap` → delete the secret
   `AEGIS_DEV_BOOTSTRAP_TOKEN`.

`aegis-dev-signing` then holds ten secrets named `AEGIS_DEV_*`. Leave them alone.

## If something fails

- **"already holds …"**: the identity exists. Nothing was changed.
- **HTTP 403 from `gh secret`**: the token lacks a permission. Edit it to add
  **Environments: Read-only** as well, then run the workflow again. Nothing was stored.
- **The job never starts**: the branch rule or the review is missing (steps 1–2).

## Rotation (only if a key may have leaked, or before the certificates expire)

1. Delete the ten `AEGIS_DEV_*` secrets of `aegis-dev-signing`.
2. Repeat steps 3–5.
3. Commit the new public keys under `keys/dev/`.
4. Installed development disks keep the old key and no longer accept updates. Replace
   them with a new disk.

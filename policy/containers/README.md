# Container signature policy of AEGIS OS (task P1-13)

Installed into the image by `image/Containerfile`:

| File | Installed as | Purpose |
|---|---|---|
| `policy.json` | `/etc/containers/policy.json` | Reject every image by default. Images from `ghcr.io/ben10-games/aegis-os` are accepted only with a valid sigstore signature by the AEGIS signing key, for that repository. Local container storage is accepted: it is where `bootc install` reads the image from, and only root can write to it. |
| `registries.d/aegis-os.yaml` | `/etc/containers/registries.d/aegis-os.yaml` | Signatures are fetched as sigstore attachments from the registry. |

The public key is written to `/usr/share/aegis/keys/aegis-os-signing.pub`, inside the
sealed root filesystem. In Phase 1 the key pair is generated for each CI run
(`scripts/signing-keys`), so an image only accepts updates signed in the same run.

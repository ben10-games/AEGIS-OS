# Development signing identity: public halves only

ADR-0015. This directory holds only public certificates and the public image key of the
persistent development identity, copied from the log of the dev-signing-bootstrap run,
so every image can be compared with them. Private keys exist only as secrets of the
GitHub environment `aegis-dev-signing` and never appear here.

`bootstrap-request` is changed (with a commit subject beginning with
`[bootstrap-dev-signing]`) only to start that workflow, after the owner has finished
steps 1–3 of `docs/operations/dev-signing-setup.md`.

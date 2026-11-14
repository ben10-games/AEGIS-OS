# Working rules for AEGIS OS

Read `PROJECT_STATE.md` before doing anything. Its "Resume here" section names the next task.
The approved design is `docs/architecture/phase-1-blueprint.md`; task IDs (P1-xx) and test
IDs (S-, B-, V-, R-) come from it.

## Rules

1. **Never commit secrets.** No private keys, tokens, passwords or recovery keys, ever.
   Phase 1 needs no stored secrets. If a task seems to need one, stop and ask the owner.
2. **Never claim a test passed without a run.** Image (B), VM (V) and reproducibility (R)
   tests only count when they ran in GitHub Actions or on a local KVM machine. Record the
   commit and run link in `PROJECT_STATE.md`.
3. **Never weaken a control to get green.** No permissive SELinux, no disabled signature
   checks, no skipped tests. Record the failure instead.
4. **Update `PROJECT_STATE.md` in the same commit as the work it describes.**
5. **Small commits**, Conventional Commits style, one task per commit series.
6. **One base distribution.** Do not introduce a second operating-system architecture.
7. Configuration shipped by AEGIS goes under `/usr/lib` in the image (`image/rootfs/usr/lib`)
   whenever the software reads it there. Anything the image changes under `/etc` must be
   listed in `tests/golden/base/etc-changes.txt` (ADR-0014).
8. The golden manifests in `tests/golden/` change only in the same commit series as the
   image change that causes them.
9. Every `uses:` in a workflow is pinned to a full commit SHA. Workflows declare minimal
   `permissions`.

## Environment facts

- Claude Cloud sessions have no KVM, no running container daemon, and cannot reach Fedora
  registries or mirrors. Do not assume otherwise; `scripts/probe-env` reports the truth.
- In the cloud, run `make static`. Everything else is verified by pushing and reading the
  GitHub Actions results.
- Installing extra tools in a cloud session may be refused. `make static` needs only
  `python3`, `pytest` and `ruff`.

## Commands

| Command | What it does | Where it works |
|---|---|---|
| `make static` | Repository rule tests + ruff | Anywhere |
| `make lint` | `static` plus shellcheck, yamllint, actionlint, gitleaks | CI, or a machine with those tools |
| `make all` | Build both images, inventory, golden manifest tests, disks, VM tests | CI, or Linux with podman and KVM |
| `make summary` | Print the evidence of the last build and test run | After `make all` |
| `scripts/probe-env` | Prints environment capabilities (read-only) | Anywhere |

## Stop and ask the owner when

- Gate G1 (sealed boot chain) fails, or reproducibility test R-02 cannot be met.
- Hosted CI runners turn out to have no usable KVM.
- A change would add a stored secret, a new external network host, or another base distribution.

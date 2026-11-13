# Developing from a restricted cloud session

A Claude Cloud session cannot build images or boot virtual machines: it has no KVM, no
running container daemon, and no access to Fedora registries. Verification therefore
happens in GitHub Actions.

## Loop

1. Read `PROJECT_STATE.md`.
2. Edit files. Run `make static` until it passes.
3. Commit (small, Conventional Commits) and push to the development branch.
4. Read the results of the workflows for that commit:
   - `lint`: static tier (S-01 to S-04).
   - `build`: images, disk image, VM boot and shutdown (B-01, B-08, V-01, V-02).
   - `probe`: runner capabilities; runs only when its own files change.
5. On failure, read the job log and the `build-and-boot-<sha>` artifact (serial console,
   guest journal, JUnit report). Fix and repeat.
6. Record passed tests in `PROJECT_STATE.md` with the commit and run link.

## Things that have gone wrong before

- A workflow with a `paths` filter does not start on the first push of a new branch.
- `lint` cancels an in-progress run of the same branch when a new commit is pushed.
  `build` runs queue instead, so each pushed commit keeps its own build and boot evidence.
- Installing tools in the cloud session (pip, go install) may be refused. `make static`
  needs only `python3`, `pytest` and `ruff`.

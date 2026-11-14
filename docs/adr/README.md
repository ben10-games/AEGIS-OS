# Architecture decision records

Each record states one decision, why it was made, and how it is checked. Status is one of
Accepted, Provisional, Open, Superseded.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-fedora-bootc-foundation.md) | Fedora bootc as the foundation | Accepted |
| [0002](0002-single-image-two-variants.md) | One image, two variants | Accepted |
| [0003](0003-stock-kernel-policy.md) | Stock Fedora kernel, no patches | Accepted |
| [0004](0004-sealed-composefs-backend.md) | Sealed images on the bootc composefs backend | Provisional |
| [0005](0005-btrfs-root.md) | btrfs root filesystem | Accepted |
| [0006](0006-build-in-container-and-input-pinning.md) | Build in a pinned container; pin every input | Accepted |
| [0007](0007-ephemeral-keys-in-phase-1.md) | Ephemeral signing keys in Phase 1 | Accepted |
| [0008](0008-firewalld.md) | firewalld as the firewall manager | Accepted |
| [0009](0009-software-trust-tiers.md) | Four software trust tiers | Accepted |
| [0010](0010-ci-as-primary-verification.md) | GitHub Actions as the primary verification environment | Accepted |
| [0011](0011-macos-scope.md) | macOS application support is out of scope | Accepted |
| [0012](0012-hardware-secure-boot-enrollment.md) | Secure Boot key enrollment on physical hardware | Open |
| [0013](0013-custom-minimal-base.md) | Custom minimal base versus stock fedora-bootc | Open |
| [0014](0014-configuration-placement.md) | Where AEGIS configuration lives | Accepted |

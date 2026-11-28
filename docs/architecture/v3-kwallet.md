# KDE Wallet with the login password (v3, Fedora package `pam-kwallet`)

The owner approved this on 2026-11-28. Applications keep saved passwords in the KDE Wallet,
for example Chrome through the system's secret storage. Without `pam-kwallet` the wallet
has no key at login, so Chrome's first start opened KDE's wallet setup assistant (v3 run
46015720076). With it, the password typed at the login screen opens the wallet.

## How it works

- **Package:** `pam-kwallet` (KDE's kwallet-pam project) comes from Fedora, in the gui install step. AEGIS adds no PAM
  configuration of its own. Fedora's SDDM login stack, `/etc/pam.d/sddm`, already lists the
  module:
  - `-auth optional pam_kwallet5.so` at authentication;
  - `-session optional pam_kwallet5.so auto_start` at session start.

  The image build fails if either line is missing, if the module is missing, or if the image
  contains a wallet or a wallet salt (`image/Containerfile.gui`).
- **Authentication:** when the password typed at the login screen is accepted, pam_kwallet
  derives the wallet key from it (PBKDF2 with SHA-512) and a random salt. The salt is
  created at the first login and kept in `~/.local/share/kwalletd/kdewallet.salt`.
- **Session start:** pam_kwallet starts the user's wallet daemon and passes it the key over
  a private socket. At the first login the daemon creates the wallet `kdewallet` with that
  key. At later logins it opens the wallet.
- **Storage:** the wallet is saved in `~/.local/share/kwalletd/kdewallet.kwl`, encrypted in
  KDE's wallet format with the derived key. The home folder is the user's own (mode 0700).

## What it guarantees

| Requirement | How it holds | Checked by |
|---|---|---|
| No hard-coded wallet password | The key is derived only from what the user types at the login screen. The image ships no wallet, no salt and no key. | Image build check; `test_wallet_is_opened_by_the_password_login` (the salt is created at the first login) |
| No plain-text credentials | A secret written to the wallet does not appear in the wallet file, and the file has KWallet's encrypted format. The login password appears in no log. | `test_wallet_is_opened_by_the_password_login` |
| Other users cannot read it | The wallet and salt files cannot be read by another account. | Same test (reads them as `nobody`) |
| No unlocking without authentication | The wallet opens only in a session started by a password login. Autologin hands over no password, so pam_kwallet does nothing. This covers the AEGIS Setup session (system user `aegis-setup`) and the Live ISO, which also switches the wallet off. Until the password is typed after a boot, nothing runs as the user. | `test_files_and_settings_survive_a_complete_power_off` (no user process at the login screen) |
| Works across a complete power-off | The same password opens the same wallet again, and the secret is still in it. | `test_wallet_opens_again_after_the_power_off` |
| Chrome needs no wallet setup | No KDE Wallet window opens when Chrome starts for the first time. | `test_v3_apps.py` (`chrome_starts`) |

These are QEMU tests on GitHub Actions, not VirtualBox.

## Limits (stated, not hidden)

- **While you are logged in, the wallet is open.** Any program running as you can ask it for
  secrets. That includes Flatpak applications allowed to talk to the secret service, as
  Chrome is. Locking the screen does not close the wallet; logging out or shutting down
  does.
- **The wallet is only as strong as your password.** The disk is not encrypted, so whoever
  can read the `.vdi` file can copy the wallet file. They can then try passwords offline.
  Use a long login password.
- **Changing the login password does not change the wallet's password.** After a password
  change, pam_kwallet derives a key the wallet does not accept. The wallet then stays
  closed, and applications ask for the old password. This build does not include KDE's
  wallet manager (KWallet Manager), so the wallet's own password cannot be changed there. To
  start over, close the applications that use the wallet, then delete
  `~/.local/share/kwalletd/kdewallet.*`. This loses the saved passwords.
- **The encryption is KDE's wallet format** (Blowfish with a password-derived key). AEGIS
  does not change it.

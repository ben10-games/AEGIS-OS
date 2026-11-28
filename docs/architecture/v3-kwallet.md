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
- **Session start:** pam_kwallet starts the user's wallet daemon, `ksecretd`, with the key
  (`ksecretd --pam-login`). The helper `pam_kwallet_init` (user unit
  `plasma-kwallet-pam.service`) then hands the session environment to it over
  `$XDG_RUNTIME_DIR/kwallet5.socket`. At the first login the daemon creates the wallet
  `kdewallet` with that key. At later logins it opens the wallet.
- **Which daemon applications talk to:** since KDE Frameworks 6.14 the former kwalletd is
  called `ksecretd`. It keeps the wallet and offers only the Secret Service API
  (`org.freedesktop.secrets`), which libsecret and Chrome use. `/usr/bin/kwalletd6` is now a
  separate wrapper for the old KWallet API: D-Bus starts it on demand, and it forwards to
  the Secret Service. AEGIS's first wallet test asked that wrapper whether `kdewallet` was
  open, which started the wrapper; it answered "no" while ksecretd had the wallet open (v3
  runs 46105970546 and 46109798171). The tests now check the Secret Service itself.
- **Storage:** the wallet is saved in `~/.local/share/kwalletd/kdewallet.kwl`, encrypted in
  KDE's wallet format with the derived key. The home folder is the user's own (mode 0700),
  and both wallet files are mode 0600.

Observed in the QEMU test (v3 run 46109798171):
- `pam_kwallet5(sddm:auth)`, `(sddm:setcred)` and `(sddm:session)` ran at the password
  login, and `ksecretd --pam-login` ran as the user.
- `kdewallet.kwl` and `kdewallet.salt` were created at the first login.
- For the AEGIS Setup autologin, pam_kwallet logged "open_session called without
  kwallet5_key": with no password, it opened nothing.

## What it guarantees

| Requirement | How it holds | Checked by |
|---|---|---|
| No hard-coded wallet password | The key is derived only from what the user types at the login screen. The image ships no wallet, no salt and no key. | Image build check; `test_wallet_is_opened_by_the_password_login` (the salt is created at the first login) |
| Opened by the login, without a prompt | The Secret Service belongs to the `ksecretd` that pam_kwallet started with `--pam-login`. Its default collection, `kdewallet`, is unlocked. A secret can be stored and read back with no prompt. | `test_wallet_is_opened_by_the_password_login` |
| No plain-text credentials | After a secret is stored through the Secret Service, the wallet file changes but does not contain the secret, and it has KWallet's encrypted format. The login password appears in no log. | `test_wallet_is_opened_by_the_password_login` |
| Other users cannot read it | The wallet and salt files cannot be read by another account. | Same test (reads them as `nobody`) |
| No unlocking without authentication | The wallet opens only in a session started by a password login. Autologin hands over no password, so pam_kwallet does nothing. This covers the AEGIS Setup session (system user `aegis-setup`) and the Live ISO, which also switches the wallet off. Until the password is typed after a boot, nothing runs as the user. | `test_files_and_settings_survive_a_complete_power_off` (no user process at the login screen) |
| Works across a complete power-off | The same password opens the same wallet again (pam-started `ksecretd`, unlocked, no prompt), and the secret is still in it. | `test_wallet_opens_again_after_the_power_off` |
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
- **Labels and attributes are not encrypted.** ksecretd keeps the names and lookup
  attributes of stored items (for example which application an entry belongs to) in
  `~/.local/share/kwalletd/kdewallet_attributes.json`, readable only by you (0600). The
  secrets themselves are only in the encrypted `kdewallet.kwl`; the test checks that the
  stored secret is in none of these files.
- **Applications using the old KWallet API** reach the wallet through the
  `kwalletd6` wrapper, which forwards to the Secret Service. That path is not tested
  here; in run 46109798171 the wrapper reported the wallet as not open. Some KDE
  applications may therefore still ask for the wallet password. Chrome uses the Secret
  Service and opened no wallet window in the tests.
- **The encryption is KDE's wallet format** (Blowfish with a password-derived key). AEGIS
  does not change it.

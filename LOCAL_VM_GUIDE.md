# AEGIS OS — running the development image in a local virtual machine

This guide takes you from nothing to a running AEGIS OS virtual machine on your own
computer, using QEMU. It covers Linux and Windows hosts.

**What you are testing.** The image is `aegis-dev`, the *development* variant of the
Phase 1 milestone M2 system: the Fedora 45 bootc base with the AEGIS identity, service
baseline, firewall, kernel hardening and SELinux policy. It is not a release, it is not
encrypted, and it has no desktop. It boots to a text console.

**What this cannot do to your computer.** The virtual machine is given exactly one
thing: the image file you downloaded. No physical disk, partition, USB device or folder
of your computer is attached, and the network is QEMU's built-in user-mode network,
which needs no change to your network settings. Deleting the downloaded folder removes
everything.

## 1. What you need

| | Recommended | Minimum |
|---|---|---|
| CPU | x86-64 with virtualization enabled in firmware (Intel VT-x or AMD-V); 2 cores for the VM | any x86-64 CPU (slow without acceleration) |
| Memory for the VM | 4 GiB | 2 GiB |
| Free disk space | 8 GiB | 5 GiB |
| Firmware for the VM | UEFI (OVMF). Legacy BIOS boot is not supported. | |
| Secure Boot in the VM | off. The image is sealed (signed UKI, verified root), but the launchers use firmware without the project's keys, so the firmware does not verify the boot chain. Secure Boot is tested in CI with keys that exist only for one run. | |
| TPM in the VM | none needed | |

The image has a virtual size of 12 GiB and grows as the guest writes to it.

Software on the host, which you install yourself (this project installs nothing):

- **Linux:** QEMU and the OVMF firmware package.
  Fedora: `qemu-system-x86-core edk2-ovmf`. Debian/Ubuntu: `qemu-system-x86 ovmf`.
  Arch: `qemu-base edk2-ovmf`. For acceleration your user needs access to `/dev/kvm`
  (usually membership of the `kvm` group).
- **Windows 10/11:** [QEMU for Windows](https://www.qemu.org/download/#windows). The
  UEFI firmware ships with it. An SSH client is already part of Windows.

## 2. Download

1. Open the repository on GitHub, then **Actions** → workflow **build** → the most
   recent run marked with a green tick that has an artifact named
   **`aegis-os-dev-qcow2`** (at the bottom of the run page). You must be signed in.
2. Download the artifact (about 1.2 GB). It is a ZIP file; extract it into an empty
   folder.

GitHub deletes artifacts after 14 days. To get a fresh one, open **Actions** → **build**
→ **Run workflow**, choose the development branch and start it. The image appears on
that run's page after about ten minutes, and only if every test passed.

The folder then contains:

| File | Purpose |
|---|---|
| `aegis-os-dev-<version>-<commit>.qcow2` | the disk image |
| `SHA256SUMS` | checksums of the image and the two launchers |
| `run-aegis-vm.sh` | launcher for Linux |
| `run-aegis-vm.ps1` | launcher for Windows |
| `IMAGE-INFO.txt` | what was built, from which commit |
| `LOCAL_VM_GUIDE.md` | this guide |

## 3. Verify the checksum

Do this before the first start. It proves the download is complete and is the file
that was tested in CI.

Linux, in the extracted folder:

```bash
sha256sum -c SHA256SUMS
```

Every line must end in `OK`.

Windows PowerShell, in the extracted folder:

```powershell
Get-Content .\SHA256SUMS
```

```powershell
Get-FileHash -Algorithm SHA256 .\*.qcow2, .\run-aegis-vm.ps1 | Format-List
```

The hash shown for each file must equal the value in `SHA256SUMS` (upper or lower case
does not matter).

## 4. Start the virtual machine

Both launchers do the same thing: start QEMU with UEFI firmware, the image as the only
disk, user-mode networking, and a text console in the window you started it from.

### Linux

```bash
chmod +x run-aegis-vm.sh
```

```bash
./run-aegis-vm.sh --image aegis-os-dev-*.qcow2
```

To also allow SSH with your own key:

```bash
./run-aegis-vm.sh --image aegis-os-dev-*.qcow2 --ssh-key ~/.ssh/id_ed25519.pub
```

Useful options: `--memory 2048`, `--cpus 4`, `--ssh-port 2222`, `--snapshot` (throw
away every change when the VM stops), `--help`.

### Windows

Open PowerShell in the extracted folder. If PowerShell refuses to run the script
because of the execution policy, allow it for this one window only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

```powershell
.\run-aegis-vm.ps1 -Image (Get-Item .\aegis-os-dev-*.qcow2).FullName
```

With SSH access:

```powershell
.\run-aegis-vm.ps1 -Image (Get-Item .\aegis-os-dev-*.qcow2).FullName -SshKey $HOME\.ssh\id_ed25519.pub
```

By default the Windows launcher uses software emulation (`-Accel tcg`), which works on
every machine but is slow: in the project's test on a 4-core Windows machine the root
prompt appeared about two and a half minutes after the start. If the Windows feature
*Windows Hypervisor Platform* is already enabled on your machine you can try
`-Accel whpx`, which is much faster; that mode has not been tested by this project, and
this guide does not ask you to enable it.

### The equivalent QEMU command

If you prefer to run QEMU yourself, this is what the Linux launcher runs (firmware
paths are Fedora's; `vars.fd` is your own copy of the `OVMF_VARS.fd` template):

```bash
qemu-system-x86_64 \
  -machine q35,accel=kvm -cpu host -smp 2 -m 4096 \
  -drive if=pflash,unit=0,format=raw,readonly=on,file=/usr/share/edk2/ovmf/OVMF_CODE.fd \
  -drive if=pflash,unit=1,format=raw,file=vars.fd \
  -drive if=virtio,format=qcow2,file=aegis-os-dev.qcow2 \
  -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 \
  -device virtio-net-pci,netdev=net0 -device virtio-rng-pci \
  -display none -serial mon:stdio -nodefaults
```

That command gives you a login prompt but no way to log in, because the image has no
password. The launchers add the options that grant access (section 5); use a launcher
unless you have a reason not to.

Never add a `-drive` or `-hda` option that names a physical disk (`/dev/sda`,
`/dev/nvme0n1`, `\\.\PhysicalDrive0`). The launchers refuse anything that is not a
regular `.qcow2` file.

## 5. Logging in

The image contains **no password and no key**. The root account is locked. Access is
granted only by what you pass when you start the VM, and only for that run:

1. **Console.** The launcher hands the guest, through the virtual firmware, a small
   systemd drop-in that makes the serial console's login service log `root` in
   automatically. That console is the window you started the launcher from. You get a
   root shell without typing anything.
   Start with `--no-autologin` (Linux) or `-NoAutologin` (Windows) to switch this off.
2. **SSH.** If you gave a public key, it is installed for `root` for this boot:

   ```bash
   ssh -p 2222 root@127.0.0.1
   ```

   The SSH server accepts keys only. The port is bound to `127.0.0.1` on your computer,
   so nothing else on your network can reach the VM.

Whoever can start the virtual machine controls these settings. That is you; the
mechanism is the virtual equivalent of sitting at the machine's own console.

## 6. What a normal boot looks like

1. A few seconds of firmware output, then the GRUB menu (it continues by itself).
2. Kernel and systemd messages scroll by. Lines start with `[  OK  ]`.
3. `aegis login: root (automatic login)` and a prompt `[root@aegis ~]#`.

With hardware acceleration (Linux with KVM) this takes well under a minute. In software
emulation it takes a few minutes.

Things to try:

```bash
cat /etc/os-release
```

```bash
getenforce
```

```bash
systemctl is-system-running
```

```bash
bootc status
```

```bash
firewall-cmd --list-all
```

```bash
touch /usr/test
```

Expected: the system identifies itself as AEGIS OS; SELinux reports `Enforcing`; the
state is `running`; `bootc status` shows the booted image; the firewall zone `aegis`
has target `DROP`; and writing under `/usr` fails with "Read-only file system".

## 7. Shutting down

In the guest:

```bash
poweroff
```

The launcher returns when the VM has stopped. To leave the console without shutting
down cleanly, press `Ctrl-A`, then `X` (this is like pulling the power cord).

During shutdown you will see "Failed to unmount ... Device or resource busy" and
"Not all file systems unmounted". This is known (BUG-3 in `PROJECT_STATE.md`): data is
synced before power-off and the next boot shows no file-system recovery.

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Linux: "no KVM acceleration" and the VM is very slow | Your user cannot open `/dev/kvm`. Enable virtualization in the computer's firmware setup, and add your user to the `kvm` group, then log in again. |
| "UEFI firmware (OVMF) not found" | Install the OVMF package (section 1), or pass `--firmware-code` and `--firmware-vars`. |
| Windows: "qemu-system-x86_64.exe not found" | Install QEMU for Windows, or pass `-QemuDir "C:\path\to\qemu"`. |
| Windows: `-Accel whpx` fails to start | The *Windows Hypervisor Platform* feature is not enabled, or another hypervisor holds it. Use the default (`tcg`). |
| "Could not set up host forwarding rule" | Port 2222 is in use on your computer. Choose another: `--ssh-port 2233` / `-SshPort 2233`. |
| Nothing appears for a long time | Without acceleration the first boot is slow. Wait five minutes before giving up. |
| The console shows a login prompt but does not log in | You started with `--no-autologin`, or ran QEMU by hand instead of with a launcher. |
| SSH says "Permission denied (publickey)" | Start the VM with `--ssh-key` / `-SshKey` pointing at the **public** key that matches the private key your SSH client uses. The key is applied at boot; restart the VM after changing it. |
| SSH warns that the host key changed | A fresh image generates new host keys. Remove the old entry: `ssh-keygen -R "[127.0.0.1]:2222"`. |
| You want a clean slate | Delete the `.qcow2` and the `.uefi-vars.*` file next to it, and extract the artifact again. |

## 9. What was verified, and where

Every published image is tested in the same GitHub Actions run before it is offered for
download; if a test fails, nothing is published. First verified in run 43719668136
(commit `aafc33a`); `PROJECT_STATE.md` lists the runs.

| What | How it was tested |
|---|---|
| The image boots with UEFI firmware and the Linux launcher | CI starts `run-aegis-vm.sh` on the exported `.qcow2` exactly as in section 4 (QEMU 11.1, Fedora's OVMF, KVM) |
| Automatic root login on the console | CI waits for the `root@aegis` prompt on the serial console |
| SSH login with a key passed at launch | CI generates a key, passes the public half to the launcher and logs in |
| The system is healthy and SELinux is enforcing | `systemctl is-system-running` is `running`, `getenforce` is `Enforcing`, no SELinux denial is logged, root's password is locked |
| Clean power-off | `poweroff` in the guest ends the launcher with exit code 0 |
| The published file is the tested file | The image is opened in snapshot mode and its SHA-256 is compared with `SHA256SUMS` before and after |
| The Windows launcher | A second job downloads the published artifact on Windows Server 2025, installs QEMU for Windows 11.1.0, verifies the checksums as in section 3, starts `run-aegis-vm.ps1` with software emulation, and checks console login, SSH login, SELinux enforcing and power-off |
| The launcher attaches nothing but the image | Tests run the Linux launcher against a stand-in for QEMU and check its complete command line; devices and directories are refused |

Not tested: Windows 10 and 11 desktop editions themselves, `-Accel whpx`, Linux
distributions other than Fedora (the firmware paths for Debian, Ubuntu, Arch and
openSUSE are in the launcher but were not exercised), QEMU versions older than 8, and
any physical hardware.

## 10. Limits of this image

- Development variant: it includes an SSH server and a self-test SELinux module that a
  release image does not have.
- No disk encryption and no signed updates yet. The root filesystem is verified (composefs
  with fs-verity), but in these launchers nothing verifies the UKI, because the firmware
  has no keys enrolled.
- No graphical desktop.
- Each build is signed by nothing; trust comes from the checksum and from the GitHub
  run that produced it.

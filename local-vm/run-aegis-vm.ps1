<#
.SYNOPSIS
  Start the AEGIS OS development image in QEMU on Windows.

.DESCRIPTION
  The virtual machine can only reach the image file given with -Image. No physical
  disk, partition or folder is attached, and networking is QEMU's user-mode network.
  This script installs nothing and changes no Windows setting.

  Login: the image contains no password and no key. This script passes two systemd
  credentials through the virtual firmware, for this run only:
    - automatic root login on the serial console (this window)
    - your SSH public key, if you give one with -SshKey

.EXAMPLE
  .\run-aegis-vm.ps1 -Image .\aegis-os-dev.qcow2

.EXAMPLE
  .\run-aegis-vm.ps1 -Image .\aegis-os-dev.qcow2 -SshKey $HOME\.ssh\id_ed25519.pub
  ssh -p 2222 root@127.0.0.1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Image,
    [string]$SshKey = "",
    [int]$SshPort = 2222,
    [int]$Memory = 4096,
    [int]$Cpus = 2,
    [ValidateSet("tcg", "whpx")][string]$Accel = "tcg",
    [switch]$Snapshot,
    [switch]$NoAutologin,
    [string]$QemuDir = "",
    [string]$SerialLog = ""
)

$ErrorActionPreference = "Stop"

# Safety: only a regular .qcow2 file is ever handed to the virtual machine.
if ($Image -match '^\\\\[.?]\\') {
    throw "'$Image' is a device path. This script only opens image files."
}
if (-not (Test-Path -LiteralPath $Image -PathType Leaf)) {
    throw "Image file '$Image' not found."
}
$imagePath = (Resolve-Path -LiteralPath $Image).Path
if ([System.IO.Path]::GetExtension($imagePath) -ne ".qcow2") {
    throw "'$imagePath' is not a .qcow2 file."
}

# Locate QEMU and the UEFI firmware that ships with it.
$candidates = @()
if ($QemuDir) { $candidates += $QemuDir }
$onPath = Get-Command "qemu-system-x86_64.exe" -ErrorAction SilentlyContinue
if ($onPath) { $candidates += (Split-Path -Parent $onPath.Source) }
if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles "qemu") }
$qemuHome = $candidates | Where-Object { Test-Path (Join-Path $_ "qemu-system-x86_64.exe") } | Select-Object -First 1
if (-not $qemuHome) {
    throw "qemu-system-x86_64.exe not found. Install QEMU for Windows or pass -QemuDir."
}
$qemu = Join-Path $qemuHome "qemu-system-x86_64.exe"
$firmwareCode = Join-Path $qemuHome "share\edk2-x86_64-code.fd"
$firmwareVars = Join-Path $qemuHome "share\edk2-i386-vars.fd"
if (-not (Test-Path $firmwareCode) -or -not (Test-Path $firmwareVars)) {
    throw "UEFI firmware not found in '$qemuHome\share' (edk2-x86_64-code.fd, edk2-i386-vars.fd)."
}

# The firmware needs a writable variable store; keep a private copy next to the image.
$varsCopy = "$imagePath.uefi-vars.fd"
if (-not (Test-Path -LiteralPath $varsCopy)) {
    Copy-Item -LiteralPath $firmwareVars -Destination $varsCopy
}

# QEMU splits option values at commas; a comma inside a file name is written twice.
function Escape([string]$Path) { return $Path.Replace(",", ",,") }

if ($SerialLog) { $serial = "file:$(Escape $SerialLog)" } else { $serial = "mon:stdio" }

$qemuArgs = @(
    "-machine", "q35,accel=$Accel",
    "-cpu", "max",
    "-smp", "$Cpus",
    "-m", "$Memory",
    "-drive", "if=pflash,unit=0,format=raw,readonly=on,file=$(Escape $firmwareCode)",
    "-drive", "if=pflash,unit=1,format=raw,file=$(Escape $varsCopy)",
    "-drive", "if=virtio,format=qcow2,file=$(Escape $imagePath)",
    "-netdev", "user,id=net0,hostfwd=tcp:127.0.0.1:$SshPort-:22",
    "-device", "virtio-net-pci,netdev=net0",
    "-device", "virtio-rng-pci",
    "-display", "none",
    "-serial", $serial,
    "-nodefaults"
)
if ($Snapshot) { $qemuArgs += "-snapshot" }
if (-not $NoAutologin) {
    $qemuArgs += @("-smbios", "type=11,value=io.systemd.credential:agetty.autologin=root")
    $qemuArgs += @("-smbios", "type=11,value=io.systemd.credential:login.noauth=yes")
}
if ($SshKey) {
    if (-not (Test-Path -LiteralPath $SshKey -PathType Leaf)) {
        throw "SSH public key file '$SshKey' not found."
    }
    $keyText = (Get-Content -LiteralPath $SshKey -Raw).Trim()
    if ($keyText -match "PRIVATE KEY") {
        throw "-SshKey must be a PUBLIC key file (usually ending in .pub)."
    }
    $keyBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($keyText + "`n"))
    $qemuArgs += @("-smbios", "type=11,value=io.systemd.credential.binary:ssh.authorized_keys.root=$keyBase64")
}

Write-Host "Starting AEGIS OS ($Accel, $Cpus CPUs, $Memory MiB). SSH: ssh -p $SshPort root@127.0.0.1"
if ($Accel -eq "tcg") {
    Write-Host "Software emulation: the first boot can take several minutes."
}
& $qemu @qemuArgs
exit $LASTEXITCODE

#!/usr/bin/python3 -I
"""AEGIS OS first-boot account provisioning (v3, M8). Runs as root, one process per
connection to /run/aegis/provision.sock (aegis-provision.socket, Accept=yes), which only
root and the group 'aegis-setup' can open.

Reads one JSON request from the socket:

    {"full_name": ..., "user_name": ..., "password": ..., "administrator": true|false,
     "time_zone": "Europe/Berlin"}

and answers one JSON line {"ok": bool, "message": str}. It creates the first account
only while the machine is unprovisioned: no /var/lib/aegis/provisioned and no account
with a UID of 1000 or more. Afterwards every request is refused. The password is passed
to chpasswd on its standard input (hashed with the system default, yescrypt), never on a
command line, and is not logged.
"""

from __future__ import annotations

import json
import pwd
import re
import subprocess
import sys
from pathlib import Path

MARKER = Path("/var/lib/aegis/provisioned")
AUTOLOGIN = Path("/etc/sddm.conf.d/90-aegis-firstboot.conf")
ZONEINFO = Path("/usr/share/zoneinfo")
USER_NAME = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
ZONE = re.compile(r"^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$")
RESERVED = {"root", "aegis-setup", "admin", "sddm", "nobody", "aegis"}


def reply(ok: bool, message: str) -> None:
    sys.stdout.write(json.dumps({"ok": ok, "message": message}) + "\n")
    sys.stdout.flush()


def provisioned() -> bool:
    return MARKER.exists() or any(1000 <= p.pw_uid < 60000 for p in pwd.getpwall())


def validate(request: dict) -> str:
    """An error message, or '' when the request is acceptable."""
    full_name = request.get("full_name")
    user_name = request.get("user_name")
    password = request.get("password")
    zone = request.get("time_zone", "UTC")
    if not isinstance(full_name, str) or not 0 < len(full_name.strip()) <= 128:
        return "Enter your full name."
    if any(c in full_name for c in ":\n\r,") or not full_name.isprintable():
        return "The full name contains characters that cannot be used."
    if not isinstance(user_name, str) or not USER_NAME.match(user_name) or user_name in RESERVED:
        return "This user name cannot be used."
    try:
        pwd.getpwnam(user_name)
        return "This user name is already taken by the system."
    except KeyError:
        pass
    if not isinstance(password, str) or not 8 <= len(password) <= 256:
        return "The password needs between 8 and 256 characters."
    if any(c in password for c in "\n\r\0") or password == user_name:
        return "This password cannot be used."
    if not isinstance(request.get("administrator", True), bool):
        return "Invalid request."
    if not isinstance(zone, str) or not ZONE.match(zone) or ".." in zone:
        return "Unknown time zone."
    if not (ZONEINFO / zone).is_file():
        return "Unknown time zone."
    return ""


def create(request: dict) -> None:
    user_name = request["user_name"]
    command = ["useradd", "--create-home", "--comment", request["full_name"].strip(),
               "--shell", "/bin/bash"]  # fmt: skip
    if request.get("administrator", True):
        command += ["--groups", "wheel"]
    subprocess.run([*command, user_name], check=True, capture_output=True)
    try:
        subprocess.run(
            ["chpasswd"],
            input=f"{user_name}:{request['password']}\n",
            text=True,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(["userdel", "--remove", user_name], check=False, capture_output=True)
        raise
    subprocess.run(
        ["timedatectl", "set-timezone", request.get("time_zone", "UTC")],
        check=False,
        capture_output=True,
    )
    MARKER.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    MARKER.write_text(f"first account: {user_name}\n")
    AUTOLOGIN.unlink(missing_ok=True)


def main() -> int:
    line = sys.stdin.readline(65536)
    if provisioned():
        reply(False, "This computer is already set up.")
        return 0
    try:
        request = json.loads(line)
    except ValueError:
        reply(False, "Invalid request.")
        return 0
    if not isinstance(request, dict):
        reply(False, "Invalid request.")
        return 0
    error = validate(request)
    if error:
        reply(False, error)
        return 0
    try:
        create(request)
    except subprocess.CalledProcessError as failure:
        print(f"aegis-provision: {failure.cmd[0]} failed: {failure.stderr}", file=sys.stderr)
        reply(False, "The account could not be created. Please try again.")
        return 0
    print(f"aegis-provision: created the first account '{request['user_name']}'", file=sys.stderr)
    reply(True, "Your account is ready. The login screen starts in a moment.")
    # Leave the setup session for the normal login screen once the reply is delivered.
    subprocess.run(
        ["systemd-run", "--on-active=3", "--unit=aegis-setup-finish", "--collect",
         "systemctl", "restart", "display-manager.service"],
        check=False,
        capture_output=True,
    )  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())

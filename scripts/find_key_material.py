#!/usr/bin/env python3
"""Fail if a private key of this build occurs anywhere on a disk image.

    scripts/find_key_material.py DISK KEYFILE...

A disk holds a whole operating system, so the words "PRIVATE KEY" appear on it
legitimately (documentation, test data). This check looks for the keys themselves:
several base64 lines of each given PEM key file, and the whole of a one-line secret
(the signing passphrase). Only the data extents of the sparse raw disk are read.
Covers keys stored as text on uncompressed file systems (the v3 disk uses none of
btrfs' compression); a key in another encoding would not be found.
Prints file names and offsets only, never key material.
"""

import os
import sys
from pathlib import Path

MIN_LINE = 40
CHUNK = 64 << 20


def patterns(path: str) -> list[bytes]:
    lines = [line.strip() for line in Path(path).read_bytes().splitlines()]
    body = [
        line
        for line in lines
        if len(line) >= MIN_LINE and not line.startswith(b"-----") and b":" not in line
    ]
    if not body:
        raise SystemExit(f"error: {path}: no key material to look for")
    return body[:2] + body[-2:-1] if len(body) > 2 else body


def data_ranges(fd: int, size: int):
    offset = 0
    while offset < size:
        try:
            start = os.lseek(fd, offset, os.SEEK_DATA)
        except OSError:  # ENXIO: only a hole is left
            return
        end = os.lseek(fd, start, os.SEEK_HOLE)
        yield start, end
        offset = end


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    disk, *keys = sys.argv[1:]
    wanted = {pattern: key for key in keys for pattern in patterns(key)}
    overlap = max(map(len, wanted))
    fd = os.open(disk, os.O_RDONLY)
    size = os.fstat(fd).st_size
    scanned = 0
    for start, end in data_ranges(fd, size):
        position, tail = start, b""
        while position < end:
            block = os.pread(fd, min(CHUNK, end - position), position)
            if not block:
                break
            window = tail + block
            for pattern, key in wanted.items():
                if pattern in window:
                    print(
                        f"error: key material of {key} found on {disk} near offset {position}",
                        file=sys.stderr,
                    )
                    return 1
            tail = window[-overlap:]
            position += len(block)
            scanned += len(block)
    print(f"ok: no key material of {len(keys)} private keys in {scanned} bytes of data on {disk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

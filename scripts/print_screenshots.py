#!/usr/bin/env python3
"""Print the screenshots of a VM test run to the job log.

    scripts/print_screenshots.py LOG_DIR [PREFIX]

Each PREFIX-*.ppm is converted to a half-size PNG and printed as base64 between markers,
so it can be recovered from the log where artifacts cannot be downloaded:
    sed -E 's/^\xef\xbb\xbf//; s/^[0-9-]+T[0-9:.]+Z ?//' log \\
      | sed -n '/^AEGIS-SCREENSHOT BEGIN NAME$/,/^AEGIS-SCREENSHOT END/p' | sed '1d;$d' | base64 -d
(GitHub logs can carry a byte-order mark at chunk boundaries; strip it with the timestamp.)
"""

import base64
import struct
import sys
import zlib
from pathlib import Path


def read_ppm(path):
    data = path.read_bytes()
    fields, position = [], 0
    while len(fields) < 4:
        while data[position : position + 1].isspace():
            position += 1
        if data[position : position + 1] == b"#":
            position = data.index(b"\n", position) + 1
            continue
        end = position
        while not data[end : end + 1].isspace():
            end += 1
        fields.append(data[position:end])
        position = end
    width, height = int(fields[1]), int(fields[2])
    return width, height, data[position + 1 :]


def half_png(width, height, pixels):
    w, h = width // 2, height // 2
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        top = (2 * y) * width * 3
        bottom = top + width * 3
        for x in range(w):
            i = 6 * x
            for c in range(3):
                rows.append(
                    (
                        pixels[top + i + c]
                        + pixels[top + i + 3 + c]
                        + pixels[bottom + i + c]
                        + pixels[bottom + i + 3 + c]
                    )
                    // 4
                )

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


prefix = sys.argv[2] if len(sys.argv) > 2 else "gui"
for path in sorted(Path(sys.argv[1]).glob(f"{prefix}-*.ppm")):
    if path.stem.endswith(("-before-click", "-resolution")):
        continue
    try:
        png = half_png(*read_ppm(path))
    except Exception as error:  # evidence only; never fail the summary
        print(f"=== screenshot {path.name}: could not convert: {error}")
        continue
    name = path.stem.removeprefix(f"{prefix}-")
    print(f"=== screenshot {name}: {len(png)} bytes (half size)")
    print(f"AEGIS-SCREENSHOT BEGIN {name}")
    encoded = base64.b64encode(png).decode()
    for start in range(0, len(encoded), 120):
        print(encoded[start : start + 120])
    print(f"AEGIS-SCREENSHOT END {name}")

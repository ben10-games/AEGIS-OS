#!/usr/bin/env python3
"""Generate the AEGIS Glass Plasma theme (GUI v2): image/rootfs-gui/usr/share/plasma/
desktoptheme/aegis-glass/.

    scripts/make_plasma_theme.py

Each surface is a Plasma frame: nine named pieces (topleft ... center) that Plasma
stretches to any size, plus the same shape with the prefix "mask-" (where KWin may blur
behind it) and soft "shadow-" pieces. The material:

- tint: the colour scheme's background (class ColorScheme-Background, which Plasma
  recolours, so the same files serve AEGIS Dark and AEGIS Light) at an opacity that
  depends on the variant: translucent/ files are used while KWin's blur is available
  (Full and Balanced Glass), the base files when it is not (Performance Glass, or no
  compositing) and are more opaque so text stays readable without blur;
- a light-facing edge: a brighter 1 px line along the top and the upper corners and a
  faint outline elsewhere;
- a soft specular sheen: a white gradient over the upper part of the surface;
- depth: a shadow around the frame.

All of this is drawn into the theme files: it is static shading, not optical refraction.
Run it after changing a value here; the generated SVGs are committed.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "image/rootfs-gui/usr/share/plasma/desktoptheme/aegis-glass"

STYLE = (
    '<style type="text/css" id="current-color-scheme">'
    ".ColorScheme-Background{color:#101826;}"
    ".ColorScheme-Text{color:#e1e8f2;}"
    ".ColorScheme-Highlight{color:#38bef0;}"
    "</style>"
)

PIECES = ("topleft", "top", "topright", "left", "center", "right",
          "bottomleft", "bottom", "bottomright")  # fmt: skip


def frame(prefix: str, ox: float, oy: float, r: float, c: float, tint: float,
          edge: float, sheen: float, solid: bool = False,
          tint_class: str = "ColorScheme-Background", underline: str = "") -> str:  # fmt: skip
    """One frame: corners of radius r, stretchable middle of size c, at offset (ox, oy).

    Pieces are separated by 1 px so each element's bounding box is exactly its piece.
    """
    out = []
    xs = (ox, ox + r + 1, ox + r + c + 2)
    ys = (oy, oy + r + 1, oy + r + c + 2)
    widths = (r, c, r)
    fill = (
        'fill="#000000"'
        if solid
        else (f'class="{tint_class}" style="fill:currentColor;fill-opacity:{tint}"')
    )
    full_h = 2 * r + c  # height of the whole surface, for the sheen gradient
    for row in range(3):
        for col in range(3):
            name = PIECES[row * 3 + col]
            x, y, w, h = xs[col], ys[row], widths[col], widths[row]
            parts = []
            if name in ("topleft", "topright", "bottomleft", "bottomright"):
                cx = x + w if "left" in name else x
                cy = y + h if "top" in name else y
                sx = x if "left" in name else x + w
                sy = y if "top" in name else y + h
                sweep = {"topleft": 1, "topright": 1, "bottomright": 1, "bottomleft": 1}[name]
                if name == "topleft":
                    d = f"M{cx},{cy} L{sx},{cy} A{r},{r} 0 0 {sweep} {cx},{sy} Z"
                elif name == "topright":
                    d = f"M{cx},{cy} L{cx},{sy} A{r},{r} 0 0 {sweep} {sx},{cy} Z"
                elif name == "bottomright":
                    d = f"M{cx},{cy} L{sx},{cy} A{r},{r} 0 0 {sweep} {cx},{sy} Z"
                else:
                    d = f"M{cx},{cy} L{cx},{sy} A{r},{r} 0 0 {sweep} {sx},{cy} Z"
                parts.append(f'<path d="{d}" {fill}/>')
                if not solid and edge > 0:
                    # Edge: an arc 0.5 px inside the outline; brighter on the upper corners.
                    rr = r - 0.5
                    if name == "topleft":
                        a = f"M{cx - rr},{cy} A{rr},{rr} 0 0 1 {cx},{cy - rr}"
                    elif name == "topright":
                        a = f"M{cx},{cy - rr} A{rr},{rr} 0 0 1 {cx + rr},{cy}"
                    elif name == "bottomright":
                        a = f"M{cx + rr},{cy} A{rr},{rr} 0 0 1 {cx},{cy + rr}"
                    else:
                        a = f"M{cx},{cy + rr} A{rr},{rr} 0 0 1 {cx - rr},{cy}"
                    strength = edge if "top" in name else edge * 0.35
                    parts.append(
                        f'<path d="{a}" fill="none" stroke="#ffffff" '
                        f'stroke-opacity="{strength:.3f}" stroke-width="1"/>'
                    )
            else:
                parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {fill}/>')
                if not solid and edge > 0:
                    if name == "top":
                        parts.append(
                            f'<rect x="{x}" y="{y}" width="{w}" height="1" fill="#ffffff" '
                            f'fill-opacity="{edge:.3f}"/>'
                        )
                    elif name == "left":
                        parts.append(
                            f'<rect x="{x}" y="{y}" width="1" height="{h}" fill="#ffffff" '
                            f'fill-opacity="{edge * 0.35:.3f}"/>'
                        )
                    elif name == "right":
                        parts.append(
                            f'<rect x="{x + w - 1}" y="{y}" width="1" height="{h}" '
                            f'fill="#ffffff" fill-opacity="{edge * 0.35:.3f}"/>'
                        )
                    elif name == "bottom":
                        parts.append(
                            f'<rect x="{x}" y="{y + h - 1}" width="{w}" height="1" '
                            f'fill="#000000" fill-opacity="{edge * 0.6:.3f}"/>'
                        )
                if underline and name == "bottom":
                    parts.append(
                        f'<rect x="{x}" y="{y + h - 2.5}" width="{w}" height="2" rx="1" '
                        f"{underline}/>"
                    )
            if not solid and sheen > 0 and name in ("top", "center", "topleft", "topright"):
                # Sheen: white fading to nothing over the upper 45% of the surface.
                gid = f"{prefix}sheen-{name}"
                top_of_surface = y if row == 0 else y - (r + 1)
                parts.insert(
                    0,
                    f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" '
                    f'y1="{top_of_surface}" x2="0" y2="{top_of_surface + full_h * 0.45}">'
                    f'<stop offset="0" stop-color="#ffffff" stop-opacity="{sheen:.3f}"/>'
                    f'<stop offset="1" stop-color="#ffffff" stop-opacity="0"/>'
                    "</linearGradient>",
                )
                if name in ("top", "center"):
                    parts.append(
                        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{gid})"/>'
                    )
            out.append(f'<g id="{prefix}{name}">{"".join(parts)}</g>')
    return "\n".join(out)


def shadow(prefix: str, ox: float, oy: float, s: float, c: float, opacity: float) -> str:
    """Shadow pieces of thickness s around a frame (darker below than above)."""
    out = []
    xs = (ox, ox + s + 1, ox + s + c + 2)
    ys = (oy, oy + s + 1, oy + s + c + 2)
    widths = (s, c, s)
    for row in range(3):
        for col in range(3):
            name = PIECES[row * 3 + col]
            if name == "center":
                continue
            x, y, w, h = xs[col], ys[row], widths[col], widths[row]
            strength = opacity * (1.25 if row == 2 else 0.7 if row == 0 else 1.0)
            gid = f"{prefix}g-{name}"
            if col != 1 and row != 1:  # corner: radial, centred on the inner corner
                cx = x + w if col == 0 else x
                cy = y + h if row == 0 else y
                grad = (
                    f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" '
                    f'cx="{cx}" cy="{cy}" r="{s}">'
                )
            else:
                if col == 1:
                    y1, y2 = (y + h, y) if row == 0 else (y, y + h)
                    grad = (
                        f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
                        f'x1="0" y1="{y1}" x2="0" y2="{y2}">'
                    )
                else:
                    x1, x2 = (x + w, x) if col == 0 else (x, x + w)
                    grad = (
                        f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
                        f'x1="{x1}" y1="0" x2="{x2}" y2="0">'
                    )
            kind = "radialGradient" if grad.startswith("<radial") else "linearGradient"
            grad += (
                f'<stop offset="0" stop-color="#000000" stop-opacity="{strength:.3f}"/>'
                f'<stop offset="0.45" stop-color="#000000" stop-opacity="{strength * 0.35:.3f}"/>'
                f'<stop offset="1" stop-color="#000000" stop-opacity="0"/></{kind}>'
            )
            out.append(
                f'<g id="{prefix}{name}">{grad}<rect x="{x}" y="{y}" width="{w}" '
                f'height="{h}" fill="url(#{gid})"/></g>'
            )
    return "\n".join(out)


def hints(margins: dict[str, int]) -> str:
    """Plasma 'hint-*' elements: their width or height sets a margin."""
    out = []
    for i, (name, value) in enumerate(margins.items()):
        out.append(
            f'<rect id="{name}" x="{2000 + i * 40}" y="0" width="{value}" height="{value}" '
            'fill="none"/>'
        )
    return "\n".join(out)


def document(body: str, size: int = 2200) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="400" '
        f'viewBox="0 0 {size} 400">\n<defs>{STYLE}</defs>\n{body}\n</svg>\n'
    )


def surface(r: int, c: int, tint: float, edge: float, sheen: float, shadow_size: int,
            shadow_opacity: float, extra: str = "") -> str:  # fmt: skip
    body = "\n".join(
        [
            frame("", 0, 0, r, c, tint, edge, sheen),
            frame("mask-", 200, 0, r, c, 1, 0, 0, solid=True),
            shadow("shadow-", 400, 0, shadow_size, c, shadow_opacity),
            extra,
        ]
    )
    return document(body)


def write(relative: str, content: str) -> None:
    path = THEME / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> None:
    # Panel (the dock): radius 18; dialogs and popups 14; tooltips 10.
    # (tint opaque variant, tint translucent variant)
    surfaces = {
        "widgets/panel-background.svg": (18, 0.90, 0.58, 0.30, 0.10, 22, 0.30),
        "dialogs/background.svg": (14, 0.94, 0.72, 0.24, 0.07, 26, 0.34),
        "widgets/tooltip.svg": (10, 0.95, 0.80, 0.20, 0.05, 14, 0.30),
        "widgets/background.svg": (14, 0.90, 0.62, 0.24, 0.07, 20, 0.28),
    }
    for name, (r, opaque, translucent, edge, sheen, s, so) in surfaces.items():
        margins = {
            "hint-top-margin": max(4, r // 2),
            "hint-bottom-margin": max(4, r // 2),
            "hint-left-margin": max(4, r // 2),
            "hint-right-margin": max(4, r // 2),
        }
        write(name, surface(r, 16, opaque, edge * 0.8, sheen * 0.6, s, so, hints(margins)))
        write(
            "translucent/" + name, surface(r, 16, translucent, edge, sheen, s, so, hints(margins))
        )

    # Task manager (dock items): rounded glass highlights and a running-app underline.
    r, c = 9, 16
    on = 'fill="#ffffff" fill-opacity="0.55"'
    accent = 'class="ColorScheme-Highlight" style="fill:currentColor;fill-opacity:1"'
    tasks = [
        frame("normal-", 0, 0, r, c, 0.0, 0.0, 0.0, underline=on),
        frame("hover-", 200, 0, r, c, 0.16, 0.25, 0.08, tint_class="ColorScheme-Text"),
        frame(
            "focus-",
            400,
            0,
            r,
            c,
            0.12,
            0.28,
            0.10,
            tint_class="ColorScheme-Text",
            underline=accent,
        ),  # fmt: skip
        frame(
            "minimized-",
            600,
            0,
            r,
            c,
            0.0,
            0.0,
            0.0,
            underline='fill="#ffffff" fill-opacity="0.25"',
        ),  # fmt: skip
        frame(
            "attention-", 800, 0, r, c, 0.35, 0.2, 0.0, tint_class="ColorScheme-Highlight"
        ),  # fmt: skip
    ]
    write("widgets/tasks.svg", document("\n".join(tasks)))

    metadata = {
        "KPlugin": {
            "Id": "aegis-glass",
            "Name": "AEGIS Glass",
            "Description": (
                "AEGIS OS Liquid Glass 2.0: frosted, edge-lit surfaces that follow the "
                "colour scheme; translucent where KWin blurs, more opaque where it does not"
            ),
            "Authors": [{"Name": "AEGIS OS"}],
            "License": "GPL-2.0-or-later",
            "Version": "2.0",
            "Website": "https://github.com/ben10-games/AEGIS-OS",
        },
        "X-Plasma-API-Minimum-Version": "6.0",
    }
    write("metadata.json", json.dumps(metadata, indent=4) + "\n")
    write(
        "plasmarc",
        "# AEGIS Glass (GUI v2). Surfaces use the translucent/ files while KWin's blur\n"
        "# is available and the more opaque base files otherwise.\n"
        "[BlurBehindEffect]\nenabled=true\n\n"
        "[AdaptiveTransparency]\nenabled=true\n",
    )


if __name__ == "__main__":
    main()

---
name: aegis-ui-designer
description: Use when designing or changing the AEGIS OS visual language - colours, wallpaper, typography, spacing, materials (translucency, blur, shadow), motion and the desktop layout - for the Plasma-based aegis-gui image.
---

# AEGIS UI designer

## Current identity (M4-GUI first iteration)

| Element | Source |
|---|---|
| Colour scheme `AEGIS Dark` (deep blue-black surfaces, cyan accent 56,190,240) | `image/rootfs-gui/usr/share/color-schemes/AEGISDark.colors` |
| Wallpaper (gradient, central glow, shield outline) | `scripts/make-wallpaper` (regenerate, never hand-edit the PNG) |
| Look-and-feel, defaults and layout | `image/rootfs-gui/usr/share/plasma/look-and-feel/org.aegisos.desktop/` |
| Font | Noto Sans |

## Principles

- **Dark first, high contrast.** Body text at least 4.5:1 against its surface; check
  every new colour pair.
- **Accent means state.** Cyan for focus and the active item; red, amber and green only
  for security state (negative, neutral, positive) so they keep their meaning.
- **Materials are GPU work.** Prefer KWin's blur and Plasma's translucent panels over
  custom shaders; measure frame time on the software renderer used in CI.
- **Motion is short.** 150-250 ms, eased; respect Plasma's global animation speed
  (including "instant") for accessibility.
- **Scale with Kirigami units** (`Kirigami.Units.gridUnit`, `largeSpacing`), never pixels.

## Workflow

1. Change the source (colour file, `scripts/make-wallpaper`, layout script).
2. Render it: wallpaper locally with the script; the desktop through the `gui` CI job.
3. Inspect the screenshots from the job log (`aegis-visual-qa`) before calling it done.

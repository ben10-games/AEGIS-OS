# AEGIS OS GUI v2: Liquid Glass 2.0, VirtualBox display integration, performance profiles

Development release of the graphical Live ISO (`AEGIS-OS-GUI-v2-Live.iso`). Measured
results and what was and was not verified are in `TEST-REPORT.txt` (this CI run) and in
`VIRTUALBOX_GUIDE.md` section 8.

## Performance

- **Rendering profiles** (`/usr/libexec/aegis/glass-profile`, the "AEGIS Appearance" app):
  - *Full Liquid Glass*: strong backdrop blur with grain, full-length animations,
    magic-lamp minimise. For hardware-accelerated graphics.
  - *Balanced Glass*: lighter blur (no grain), animations at 75 % length, squash
    minimise. The default when the graphics card renders.
  - *Performance Glass*: no backdrop blur (the theme switches to its more opaque
    surfaces), animations at half length, no minimise or open/close animation. The default
    with software rendering (llvmpipe), e.g. VirtualBox without 3D acceleration.
  - *Automatic* (default): picks Balanced or Performance from the renderer KWin reports.
- The Baloo file indexer is off by default (background CPU, memory and disk writes; its
  index is lost at power-off in the live system).
- `/usr/libexec/aegis/graphics-report [--measure]`: renderer, driver, profile, and a frame
  rate measurement with the AEGIS Frame Meter, for bug reports from real machines.

## VirtualBox

- Fedora's VirtualBox guest tools (`virtualbox-guest-additions` 7.2) in the Live ISO, for
  automatic display resizing and full screen with the VMSVGA graphics controller. They
  start only inside VirtualBox.
- The live login helper no longer forces 1920x1080 inside VirtualBox, where the host now
  sets the size; other hypervisors keep the 1920x1080 start size.

## Liquid Glass 2.0 (appearance)

- **AEGIS Glass** Plasma theme: frosted surfaces with a light-facing top edge, a faint
  outline, a soft top sheen and soft shadows, for the dock, popups, notifications,
  tooltips and widgets. Translucent while KWin blurs (Full and Balanced Glass), more
  opaque without blur (Performance Glass). The surfaces take their colour from the
  colour scheme, so they follow AEGIS Dark and AEGIS Light. The glass is backdrop blur
  and drawn shading; it does not refract light.
- **AEGIS Light** colour scheme next to AEGIS Dark; the accent colour follows the
  wallpaper.
- **Dock**: AEGIS Glass task highlights with a running-app underline (accent colour for
  the active app), hides when a window would cover it and returns at the bottom edge,
  stays centred at every screen size. Pinned: Files, Terminal, System Settings, AEGIS
  Appearance.
- **Launcher**: Application Dashboard (full-screen glass overlay) with search, recent
  applications and keyboard navigation, behind the AEGIS mark.
- **Windows**: borderless Breeze decorations with larger, softer shadows and centred
  titles.

## Not in this release

- Optical refraction (bending of the background) is not implemented.
- Translucent Dolphin sidebars (not supported by the Breeze application style).
- Persistence of installed applications or settings across restarts.

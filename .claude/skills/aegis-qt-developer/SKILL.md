---
name: aegis-qt-developer
description: Use when writing Qt 6 / QML / Kirigami code for AEGIS OS - Plasma applets for the dock or launcher, Kirigami applications such as the Control Center or security dashboard, or System Settings modules - including how to structure, test and package it into the aegis-gui image.
---

# AEGIS Qt developer

## Structure

- Applications: Kirigami (`org.kde.kirigami`), C++ backend only where QML cannot reach
  the data safely; one QML module per application; no business logic in delegates.
- Plasma components: Plasma 6 applets (`metadata.json`, `contents/ui/main.qml`),
  installed under `/usr/share/plasma/plasmoids/` in `image/rootfs-gui/`.
- Settings: KCMs (`KQuickConfigModule`) so they appear in System Settings.

## Rules

- Never present placeholder data as real. If a value cannot be read, show that it is
  unknown and why.
- Read system state through documented interfaces (files in `/sys`, D-Bus services); no
  shelling out to root tools from the UI.
- Every component gets a test: `qmltestrunner` for QML logic where possible, and an
  assertion in `tests/vm/test_gui.py` for its presence and behaviour in the real session.
- Lint QML with `qmllint` (qt6-qtdeclarative) before committing.

## Packaging into the image

Add files under `image/rootfs-gui/` (pure QML) or a build stage in
`image/Containerfile.gui` (compiled code; build tools must stay out of the final image),
then run the `gui` CI job.

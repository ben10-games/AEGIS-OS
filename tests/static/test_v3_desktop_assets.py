"""v3 M10, the hybrid AEGIS desktop: the files that define it are complete and consistent.
What they do on a running system is tested in tests/vm/test_v3_desktop.py."""

import json

GUI = "image/rootfs-gui"
LAYOUT = (
    f"{GUI}/usr/share/plasma/look-and-feel/org.aegisos.desktop/contents/layouts/"
    "org.kde.plasma.desktop-layout.js"
)
DEFAULTS = f"{GUI}/usr/share/plasma/look-and-feel/org.aegisos.desktop/contents/defaults"
PLASMOIDS = f"{GUI}/usr/share/plasma/plasmoids"
THEME = f"{GUI}/usr/share/sddm/themes/aegis"


def test_layout_has_a_top_bar_and_the_dock(root):
    layout = (root / LAYOUT).read_text()
    bar, dock = layout.split("// --- dock", 1)
    assert 'bar.location = "top"' in bar and 'bar.opacity = "translucent"' in bar
    for widget in (
        "org.aegisos.activewindow",
        "org.kde.plasma.appmenu",
        "org.kde.milou",
        "org.kde.plasma.systemtray",
        "org.aegisos.quicksettings",
        "org.kde.plasma.digitalclock",
    ):
        assert f'"{widget}"' in bar, widget
    assert 'search.globalShortcut = "Meta+S"' in bar
    assert 'quick.globalShortcut = "Meta+A"' in bar
    assert 'panel.location = "bottom"' in dock and "panel.floating = true" in dock
    for widget in ("org.kde.plasma.kickoff", "org.kde.plasma.icontasks", "org.aegisos.security"):
        assert f'"{widget}"' in dock, widget


def test_new_widgets_are_complete(root):
    for widget in ("org.aegisos.quicksettings", "org.aegisos.activewindow"):
        metadata = json.loads((root / PLASMOIDS / widget / "metadata.json").read_text())
        assert metadata["KPlugin"]["Id"] == widget
        assert metadata["KPackageStructure"] == "Plasma/Applet"
        main = (root / PLASMOIDS / widget / "contents/ui/main.qml").read_text()
        assert "PlasmoidItem" in main
    quick = root / PLASMOIDS / "org.aegisos.quicksettings/contents/ui"
    main = (quick / "main.qml").read_text()
    for part in ("Tile.qml", "DndTile.qml"):
        assert (quick / part).is_file(), part
    assert 'source: "DndTile.qml"' in main, "Do Not Disturb must load on its own"
    for action in (
        "scheme ",
        "nightlight ",
        "glass ",
        "spectacle --region",
        "loginctl lock-session",
    ):
        assert action in main, action
    tile = (quick / "Tile.qml").read_text()
    assert "Accessible.name" in tile and "Keys.onSpacePressed" in tile
    assert (root / GUI / "usr/share/icons/hicolor/scalable/apps/aegis-quicksettings.svg").is_file()


def test_quick_settings_helper_needs_no_privileges(root):
    tool = (root / GUI / "usr/libexec/aegis/quick-settings").read_text()
    assert tool.startswith("#!/usr/bin/env bash\n")
    for command in ("status)", "scheme)", "glass)", "nightlight)"):
        assert command in tool, command
    assert "plasma-apply-colorscheme AEGISDark" in tool
    assert "plasma-apply-colorscheme AEGISLight" in tool
    for word in ("sudo", "pkexec", "/etc/"):
        assert word not in tool, word


def test_login_screen_theme(root):
    metadata = (root / THEME / "metadata.desktop").read_text()
    assert "QtVersion=6" in metadata and "MainScript=Main.qml" in metadata
    main = (root / THEME / "Main.qml").read_text()
    # The password field has the focus from the start: typing the password and Enter logs
    # in (the VM tests and keyboard users rely on it).
    assert "password.forceActiveFocus()" in main and "onAccepted: root.logIn()" in main
    assert "sddm.login(" in main and "onLoginFailed" in main
    assert "MultiEffect" not in main and "ShaderEffect" not in main, "software rendering"
    selection = (root / GUI / "usr/lib/sddm/sddm.conf.d/zz-aegis-theme.conf").read_text()
    assert "[Theme]\nCurrent=aegis" in selection


def test_shortcuts_typeface_and_window_switcher(root):
    shortcuts = (root / GUI / "etc/xdg/kglobalshortcutsrc").read_text()
    assert "Overview=Meta+Tab\\tMeta+W," in shortcuts
    assert "[services][systemsettings.desktop]\n_launch=Meta+I" in shortcuts
    assert "RectangularRegionScreenShot=Meta+Shift+S" in shortcuts
    # In /etc/xdg: the look-and-feel defaults do not carry fonts or the switcher layout.
    kdeglobals = (root / GUI / "usr/share/aegis/xdg/kdeglobals.aegis").read_text()
    assert (
        "kdeglobals.aegis >> /etc/xdg/kdeglobals" in (root / "image/Containerfile.gui").read_text()
    )
    assert "[General]\nfont=Inter,10," in kdeglobals
    assert "[TabBox]\nLayoutName=thumbnail_grid" in (root / GUI / "etc/xdg/kwinrc").read_text()

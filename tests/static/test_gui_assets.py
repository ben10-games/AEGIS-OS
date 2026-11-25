"""GUI v1: the AEGIS design assets are complete and consistent (no VM needed).

The rendered result is checked in CI (tests/vm/test_gui.py, screenshots); these tests
catch broken references before an image is built.
"""

import json
import re
import struct

GUI = "image/rootfs-gui"
STYLE = f"{GUI}/usr/lib64/qt6/qml/org/aegisos/style"
PLASMOID = f"{GUI}/usr/share/plasma/plasmoids/org.aegisos.security"
LAYOUT = (
    f"{GUI}/usr/share/plasma/look-and-feel/org.aegisos.desktop/contents/layouts/"
    "org.kde.plasma.desktop-layout.js"
)


def test_qml_module_lists_existing_files(root):
    entries = (root / STYLE / "qmldir").read_text().splitlines()
    assert entries[0] == "module org.aegisos.style"
    for line in entries[1:]:
        if not line.strip():
            continue
        *_, file = line.split()
        assert (root / STYLE / file).is_file(), file
    assert "pragma Singleton" in (root / STYLE / "Tokens.qml").read_text()


def test_blur_tokens_match_the_kwin_defaults(root):
    tokens = (root / STYLE / "Tokens.qml").read_text()
    kwinrc = (root / GUI / "etc/xdg/kwinrc").read_text()
    strength = re.search(r"kwinStrength: (\d+)", tokens).group(1)
    noise = re.search(r"kwinNoise: (\d+)", tokens).group(1)
    assert f"BlurStrength={strength}" in kwinrc
    assert f"NoiseStrength={noise}" in kwinrc
    assert "blurEnabled=true" in kwinrc


def test_every_material_has_an_opaque_fallback(root):
    tokens = (root / STYLE / "Tokens.qml").read_text()
    assert "reducedTransparency: softwareRenderer" in tokens
    assert tokens.count("fill: opaque ?") == 3


def test_security_widget_is_complete_and_in_the_dock(root):
    metadata = json.loads((root / PLASMOID / "metadata.json").read_text())
    assert metadata["KPlugin"]["Id"] == "org.aegisos.security"
    assert metadata["KPackageStructure"] == "Plasma/Applet"
    main = (root / PLASMOID / "contents/ui/main.qml").read_text()
    assert "import org.aegisos.style" in main
    assert "/usr/libexec/aegis/security-status" in main
    layout = (root / LAYOUT).read_text()
    assert 'panel.addWidget("org.aegisos.security")' in layout
    assert 'writeConfig("icon", "aegis-os")' in layout
    for icon in ("aegis-os", "aegis-security"):
        assert (root / GUI / f"usr/share/icons/hicolor/scalable/apps/{icon}.svg").is_file()


def test_security_helper_is_read_only_and_unprivileged(root):
    text = (root / GUI / "usr/libexec/aegis/security-status").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for forbidden in (
        "sudo",
        "pkexec",
        "setenforce",
        " rm ",
        "chmod",
        "systemctl start",
        "systemctl stop",
        "bootc switch",
        "bootc upgrade",
    ):
        assert forbidden not in code, forbidden
    # It writes nowhere: the only redirection target is /dev/null.
    assert not re.findall(r">\s*/(?!dev/null)", code)


def test_wallpaper_is_1920x1080_png(root):
    data = (root / GUI / "usr/share/wallpapers/AEGIS/contents/images/1920x1080.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (1920, 1080)


THEME = f"{GUI}/usr/share/plasma/desktoptheme/aegis-glass"
PIECES = ("topleft", "top", "topright", "left", "center", "right",
          "bottomleft", "bottom", "bottomright")  # fmt: skip


def test_glass_theme_frames_are_complete(root):
    """Every AEGIS Glass surface has all nine pieces, a blur mask and shadows, in both the
    translucent (blur available) and the more opaque (no blur) variant."""
    for variant in ("", "translucent/"):
        for name in ("widgets/panel-background", "dialogs/background", "widgets/tooltip"):
            ids = set(
                re.findall(r'id="([^"]+)"', (root / THEME / f"{variant}{name}.svg").read_text())
            )
            for piece in PIECES:
                assert piece in ids and f"mask-{piece}" in ids, (variant, name, piece)
                if piece != "center":
                    assert f"shadow-{piece}" in ids, (variant, name, piece)
    tasks = set(re.findall(r'id="([^"]+)"', (root / THEME / "widgets/tasks.svg").read_text()))
    for state in ("normal", "hover", "focus", "minimized", "attention"):
        assert f"{state}-center" in tasks, state


def test_glass_theme_is_the_default_and_regenerates_identically(root, tmp_path):
    defaults = (
        root / GUI / "usr/share/plasma/look-and-feel/org.aegisos.desktop/contents/defaults"
    ).read_text()
    assert "[plasmarc][Theme]\nname=aegis-glass" in defaults
    before = {p: p.read_bytes() for p in (root / THEME).rglob("*") if p.is_file()}
    import subprocess

    subprocess.run(["python3", str(root / "scripts/make_plasma_theme.py")], check=True)
    after = {p: p.read_bytes() for p in (root / THEME).rglob("*") if p.is_file()}
    assert before == after, "the committed theme differs from scripts/make_plasma_theme.py"


def test_glass_profiles_cover_every_choice(root):
    tool = (root / GUI / "usr/libexec/aegis/glass-profile").read_text()
    for profile in ("auto", "full", "balanced", "performance"):
        assert f"{profile})" in tool or f"{profile} |" in tool, profile
    assert "llvmpipe" in tool and "blurEnabled false" in tool
    assert "sudo" not in tool and "pkexec" not in tool, "profiles must not need admin rights"
    autostart = (root / GUI / "etc/xdg/autostart/aegis-glass-profile.desktop").read_text()
    assert "Exec=/usr/libexec/aegis/glass-profile session" in autostart
    layout = (root / LAYOUT).read_text()
    assert 'panel.addWidget("org.kde.plasma.kickerdash")' in layout
    assert 'panel.hiding = "dodgewindows"' in layout

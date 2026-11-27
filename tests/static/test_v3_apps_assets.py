"""v3 M11/M12: the Welcome tour and the App Center stay unprivileged, use only the
user's own Flatpak installation, and never present verification as a safety claim."""

import re

APPCENTER = "apps/aegis-appcenter"
WELCOME = "apps/aegis-welcome"


def sources(root, directory):
    return {
        p: p.read_text()
        for p in (root / directory).rglob("*")
        if p.suffix in {".cpp", ".qml", ".js"}
    }


def test_app_center_uses_only_the_user_installation(root):
    code = (root / APPCENTER / "main.cpp").read_text()
    calls = re.findall(
        r"\{QStringLiteral\(\"(install|uninstall|update|list|remote-ls|remote-info|info)\"\)[^}]*\}",
        code,
    )
    assert calls, "no flatpak calls found"
    for match in re.finditer(
        r"\{QStringLiteral\(\"(?:install|uninstall|update|list|remote-ls|remote-info|info)\"\)([^}]*)\}",
        code,
    ):
        assert '"--user"' in match.group(1), match.group(0)
    for text in sources(root, APPCENTER).values():
        for word in ("--system", "sudo", "pkexec", "polkit"):
            assert word not in text, word


def test_verification_is_never_called_safe(root):
    for directory in (APPCENTER, WELCOME):
        for path, text in sources(root, directory).items():
            for sentence in re.split(r"(?<=[.!?])\s", text.replace("\n", " ")):
                if re.search(r"\bsafe\b", sentence, re.IGNORECASE):
                    assert re.search(r"does not|not checked|never", sentence), (
                        path,
                        sentence,
                    )
    details = (root / APPCENTER / "Details.qml").read_text()
    assert "Verified publisher" in details and "Publisher not verified" in details


def test_updates_are_only_announced(root):
    service = (root / APPCENTER / "aegis-appcenter-updates.service").read_text()
    assert "ExecStart=/usr/bin/aegis-appcenter --check-updates" in service
    code = (root / APPCENTER / "main.cpp").read_text()
    check = code.split("static int checkUpdatesAndNotify()", 1)[1].split("\n}\n", 1)[0]
    assert "remote-ls" in check and "Notify" in check
    assert '"install"' not in check and '"update"' not in check, "the check must not apply updates"


def test_welcome_is_unprivileged_and_watch_script_is_read_only(root):
    for text in sources(root, WELCOME).values():
        for word in ("sudo", "pkexec", "/etc/"):
            assert word not in text, word
    watch = (root / WELCOME / "watch.js").read_text()
    # The only change it makes to any window: keeping the tour's own window above.
    assignments = re.findall(r"window\.(\w+)\s*=", watch)
    assert assignments == ["frameGeometry", "keepAbove"], assignments
    # Both only for the tour's own window.
    assert "function placeTour(window)" in watch
    assert watch.count('=== "org.aegisos.welcome"') == 1
    assert 'resourceClass) === "org.aegisos.welcome"' in watch
    main = (root / WELCOME / "main.cpp").read_text()
    assert "GenericStateLocation" in main and "welcome.json" in main


def test_welcome_scenes_are_all_built_and_have_exercises(root):
    cmake = (root / WELCOME / "CMakeLists.txt").read_text()
    for scene in ("Awakens", "Desktop", "Workspace", "MakeItYours", "Apps", "Security", "Ready"):
        assert f"scenes/{scene}.qml" in cmake, scene
        assert (root / WELCOME / "scenes" / f"{scene}.qml").is_file(), scene
    steps = set()
    for path in (root / WELCOME).rglob("*.qml"):
        steps |= set(re.findall(r'complete\("([a-z]+\.[a-z]+)"\)', path.read_text()))
    assert len(steps) == 14, sorted(steps)

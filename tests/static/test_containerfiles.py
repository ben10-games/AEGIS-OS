"""Supply-chain rules for container builds: no floating base images."""

import re

FROM = re.compile(r"^FROM\s+(\S+)(?:\s+[Aa][Ss]\s+(\S+))?", flags=re.MULTILINE)
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def containerfiles(files):
    found = [p for p in files if p.name.startswith("Containerfile")]
    assert found, "no Containerfiles found"
    return found


def test_base_lock_pins_by_digest(root):
    lines = (root / "image" / "base.lock").read_text().splitlines()
    values = [line.split("=", 1)[1] for line in lines if line.startswith("BASE_IMAGE=")]
    assert len(values) == 1, "image/base.lock must define BASE_IMAGE exactly once"
    assert DIGEST.search(values[0]), "BASE_IMAGE must end in @sha256:<64 hex digits>"


def test_from_lines_never_use_a_floating_tag(files):
    """A FROM may name a build argument, an earlier stage, or an image pinned by digest."""
    problems = []
    for path in containerfiles(files):
        stages = set()
        for image, alias in FROM.findall(path.read_text()):
            pinned = image.startswith("${") or image in stages or DIGEST.search(image)
            if not pinned:
                problems.append(f"{path.name}: 'FROM {image}' is not pinned")
            if alias:
                stages.add(alias)
    assert not problems, "\n".join(problems)


def test_build_arguments_for_base_images_have_no_remote_default(files):
    """Defaults may point at locally built images only; remote bases come from base.lock."""
    for path in containerfiles(files):
        for name, default in re.findall(r"^ARG\s+(BASE\w*)=(\S+)", path.read_text(), flags=re.M):
            assert default.startswith("localhost/"), (
                f"{path.name}: ARG {name} defaults to remote image {default}"
            )


def test_base_pin_is_the_upstream_digest(root):
    """The build may use the upstream registry or the project's mirror, never another image."""
    lock = dict(
        line.split("=", 1)
        for line in (root / "image" / "base.lock").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    repository, digest = lock["BASE_IMAGE"].split("@")
    assert digest == lock["UPSTREAM_DIGEST"], "BASE_IMAGE must carry the upstream digest"
    assert repository in (lock["UPSTREAM_REPOSITORY"], lock["MIRROR_REPOSITORY"])
    assert lock["MIRROR_REPOSITORY"] == lock["MIRROR_REPOSITORY"].lower()


# --- P1-15: packages come from the locked inputs only ------------------------------------

ALL_CONTAINERFILES = [
    "image/Containerfile",
    "image/Containerfile.dev",
    "image/Containerfile.seal",
    "image/Containerfile.update",
    "image/Containerfile.gui",
    "image/Containerfile.live",
    "image/Containerfile.v3",
    "build/builder/Containerfile",
]


def test_no_containerfile_installs_from_a_repository(root):
    """Every dnf install goes through install-locked; no name is resolved at build time."""
    for name in ALL_CONTAINERFILES:
        text = (root / name).read_text().replace("\\\n", " ")
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            assert not re.search(r"\b(dnf|yum|microdnf|rpm-ostree)\b[^&;|]*\binstall\b", line), (
                f"{name}: installs from a repository: {line.strip()}"
            )
            assert "curl " not in line and "wget " not in line, f"{name}: downloads: {line}"


def test_locked_install_steps_match_the_inputs(root):
    """Each install step of rpms.in.yaml is installed from its own directory of the lock."""
    mounts = {
        "image/Containerfile": {"base"},
        "image/Containerfile.dev": {"dev", "dev-policy"},
        "image/Containerfile.gui": {"gui"},
        "image/Containerfile.live": {"live"},
        "image/Containerfile.v3": {"apps-build"},
        "build/builder/Containerfile": {"builder"},
    }
    for name, steps in mounts.items():
        text = (root / name).read_text()
        found = set(re.findall(r"--mount=type=bind,from=rpms,source=([a-z-]+),", text))
        assert found == steps, f"{name}: mounts locked steps {found}, expected {steps}"


def test_install_locked_disables_repositories_and_checks_sums(root):
    text = (root / "image" / "build" / "install-locked").read_text()
    assert "sha256sum --check --strict" in text
    assert text.count("--disablerepo='*'") == 2
    assert "dnf -y --disablerepo='*' --setopt=install_weak_deps=False install" in text


def test_image_builds_have_no_network(root):
    """All image and builder builds pass the locked options (no network, fixed time)."""
    for name in ("scripts/build-image", "scripts/build-builder", "scripts/build-live-iso"):
        text = (root / name).read_text()
        builds = text.count("podman build \\\n")
        assert builds > 0
        assert text.count('"${locked[@]}"') == builds, f"{name}: a build without the lock options"
        assert "--network=none" in text and '--build-context "rpms=${inputs}"' in text

"""S-03: CI workflows pin third-party actions by commit and declare minimal permissions."""

import re

USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def workflows(root):
    found = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    assert found, "no workflows found"
    return found


def test_actions_are_pinned_to_a_commit_sha(root):
    problems = []
    for path in workflows(root):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            match = USES.match(line)
            if not match:
                continue
            ref, trailer = match.groups()
            if ref.startswith("./"):
                continue
            if not PINNED.match(ref):
                problems.append(
                    f"{path.name}:{number}: '{ref}' is not pinned to a 40-character SHA"
                )
            elif "# v" not in trailer:
                problems.append(f"{path.name}:{number}: add a '# vX.Y.Z' comment after the SHA")
    assert not problems, "\n".join(problems)


def test_workflows_declare_top_level_permissions(root):
    for path in workflows(root):
        assert re.search(r"^permissions:", path.read_text(), flags=re.MULTILINE), (
            f"{path.name}: missing top-level 'permissions:'"
        )


def test_no_pull_request_target_trigger(root):
    for path in workflows(root):
        assert "pull_request_target" not in path.read_text(), (
            f"{path.name}: pull_request_target runs untrusted code with secrets"
        )


def test_checkout_does_not_persist_credentials(root):
    for path in workflows(root):
        text = path.read_text()
        assert text.count("actions/checkout@") == text.count("persist-credentials: false"), (
            f"{path.name}: every checkout must set 'persist-credentials: false'"
        )


def test_only_the_mirror_workflow_may_write_packages(root):
    """Write access to the container registry is confined to one reviewed job."""
    for path in workflows(root):
        text = path.read_text()
        if path.name == "mirror-base.yml":
            assert text.count("packages: write") == 1
            assert "workflow_dispatch" in text
            assert "delete" not in text.lower().replace("deleted by this workflow", "")
        else:
            assert "packages: write" not in text, f"{path.name}: must not write packages"
        assert ": write-all" not in text
        assert "contents: write" not in text, f"{path.name}: must not write to the repository"

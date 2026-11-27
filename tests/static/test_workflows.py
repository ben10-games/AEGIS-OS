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


PACKAGE_WRITERS = {
    "mirror-base.yml": "mirror",
    "build.yml": "build-and-boot",
    "update-inputs.yml": "resolve",
}
# Steps other than registry logins that may see the token, each reviewed.
TOKEN_STEPS = {
    ("mirror-base.yml", "Copy the pinned image, keeping its digest"),
    # Read-only (actions: read) check of the signing environments' protection (ADR-0015).
    ("dev-signing-bootstrap.yml", "Check the environments' protection (read-only)"),
}
JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$", re.MULTILINE)


def jobs_of(text: str) -> dict[str, str]:
    """Top-level jobs of a workflow and their text (no YAML library needed)."""
    body = text.split("\njobs:\n", 1)[1]
    names = list(JOB.finditer(body))
    return {
        match.group(1): body[match.end() : names[i + 1].start() if i + 1 < len(names) else None]
        for i, match in enumerate(names)
    }


def test_package_write_is_confined_to_reviewed_jobs(root):
    """Write access to the container registry: only the base mirror job and the build job
    that publishes signed images, each granted at job level, never at workflow level."""
    for path in workflows(root):
        text = path.read_text()
        header = text.split("\njobs:\n", 1)[0]
        assert "packages: write" not in header, f"{path.name}: workflow-level packages: write"
        writers = [name for name, job in jobs_of(text).items() if "packages: write" in job]
        expected = [PACKAGE_WRITERS[path.name]] if path.name in PACKAGE_WRITERS else []
        assert writers == expected, f"{path.name}: jobs writing packages: {writers}"
        assert ": write-all" not in text
        assert "contents: write" not in text, f"{path.name}: must not write to the repository"


def test_registry_token_is_used_only_by_login_steps(root):
    """The job token reaches only the steps that log in to the registry."""
    for path in workflows(root):
        for job_name, job in jobs_of(path.read_text()).items():
            for step in re.split(r"\n      - ", job)[1:]:
                if "GITHUB_TOKEN" in step:
                    name = re.search(r"name:\s*(.+)", step)
                    allowed = name and (
                        name.group(1).startswith("Log in")
                        or (path.name, name.group(1)) in TOKEN_STEPS
                    )
                    assert allowed, f"{path.name}:{job_name}: {name and name.group(1)}"

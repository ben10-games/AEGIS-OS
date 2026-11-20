"""P1-15: the RPM input lock (scripts/rpmlock.py) fails closed.

These tests use synthetic files, so they run anywhere. scripts/test-inputs repeats the
important cases on real Fedora RPMs in CI (signatures, offline installation).
"""

import hashlib
import importlib.util
import sys

import pytest


@pytest.fixture(scope="module")
def rpmlock(root):
    spec = importlib.util.spec_from_file_location("rpmlock", root / "scripts" / "rpmlock.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["rpmlock"] = module
    spec.loader.exec_module(module)
    return module


BASE = "ghcr.io/ben10-games/aegis-os/fedora-bootc@sha256:" + "a" * 64
CACHE = "ghcr.io/ben10-games/aegis-os/rpm-inputs@sha256:" + "b" * 64
INPUTS = b"base:\n  - audit\ndev-policy:\n  - selinux-policy-devel@selinux-policy\n"
BASE_LOCK = f"UPSTREAM_TAG=45\nBASE_IMAGE={BASE}\n"


@pytest.fixture
def tree(tmp_path, rpmlock):
    """A lock with three packages and a directory holding exactly those files."""
    files = {
        ("base", "audit", "4.1.2", "1.fc45", "x86_64"): b"audit rpm",
        ("base", "audit-libs", "4.1.2", "1.fc45", "x86_64"): b"audit-libs rpm",
        ("dev-policy", "selinux-policy-devel", "45.24", "1.fc45", "noarch"): b"policy rpm",
    }
    directory = tmp_path / "rpms"
    packages = []
    for (step, name, version, release, arch), data in files.items():
        file = f"{name}-{version}-{release}.{arch}.rpm"
        (directory / step).mkdir(parents=True, exist_ok=True)
        (directory / step / file).write_bytes(data)
        location = f"Packages/{name[0]}/{file}"
        packages.append(
            rpmlock.Package(
                step,
                name,
                f"{version}-{release}",
                arch,
                hashlib.sha256(data).hexdigest(),
                len(data),
                "updates",
                location,
            )
        )
    lock = rpmlock.Lock(
        BASE, rpmlock.inputs_digest(INPUTS), "2026-11-20T10:00:00Z", CACHE, packages
    )
    headers = tmp_path / "headers.tsv"
    headers.write_text(
        "".join(
            f"{p.path}\t{p.name}\t0\t{p.version}\t{p.release}\t{p.arch}\t{rpmlock.SIGNATURE_OK}\n"
            for p in packages
        )
    )
    return {"lock": lock, "dir": directory, "headers": headers, "packages": packages}


def verify(rpmlock, tree, headers=True):
    return rpmlock.verify_dir(
        tree["lock"], tree["dir"], tree["headers"] if headers else None, write_sums=False
    )


def refused(rpmlock, tree, message, headers=True):
    with pytest.raises(rpmlock.InputError, match=message):
        verify(rpmlock, tree, headers)


def test_the_lock_round_trips(rpmlock, tree):
    lock = tree["lock"]
    assert rpmlock.parse_lock(lock.text()) == lock


def test_an_intact_tree_verifies(rpmlock, tree):
    assert verify(rpmlock, tree) == 3


def test_checksums_are_written_only_after_success(rpmlock, tree):
    rpmlock.verify_dir(tree["lock"], tree["dir"], tree["headers"], write_sums=True)
    sums = (tree["dir"] / "base" / "SHA256SUMS").read_text().splitlines()
    assert len(sums) == 2 and all(line.endswith(".rpm") for line in sums)
    # The written file is ignored by the next verification.
    assert verify(rpmlock, tree) == 3


def test_a_tampered_rpm_is_refused(rpmlock, tree):
    path = tree["dir"] / tree["packages"][0].path
    path.write_bytes(b"audit rpX")  # same size, other content
    refused(rpmlock, tree, "SHA-256 differs")


def test_a_truncated_rpm_is_refused(rpmlock, tree):
    (tree["dir"] / tree["packages"][0].path).write_bytes(b"audit")
    refused(rpmlock, tree, "size 5, locked 9")


def test_a_missing_rpm_is_refused(rpmlock, tree):
    (tree["dir"] / tree["packages"][1].path).unlink()
    refused(rpmlock, tree, "locked but missing")


def test_a_missing_directory_is_refused(rpmlock, tree, tmp_path):
    with pytest.raises(rpmlock.InputError, match="missing"):
        rpmlock.verify_dir(tree["lock"], tmp_path / "absent", None, False)


def test_an_extra_rpm_is_refused(rpmlock, tree):
    (tree["dir"] / "base" / "newer-2.0-1.fc45.x86_64.rpm").write_bytes(b"x")
    refused(rpmlock, tree, "not in the lock")


def test_an_extra_step_directory_is_refused(rpmlock, tree):
    (tree["dir"] / "surprise").mkdir()
    refused(rpmlock, tree, "unexpected directory")


def test_a_symbolic_link_is_refused(rpmlock, tree):
    target = tree["dir"] / tree["packages"][0].path
    target.unlink()
    target.symlink_to("/etc/passwd")
    refused(rpmlock, tree, "symbolic link")


def test_an_unsigned_rpm_is_refused(rpmlock, tree):
    text = tree["headers"].read_text().replace(rpmlock.SIGNATURE_OK, "digests OK", 1)
    tree["headers"].write_text(text)
    refused(rpmlock, tree, "signature check: digests OK")


def test_a_bad_signature_is_refused(rpmlock, tree):
    text = tree["headers"].read_text().replace(rpmlock.SIGNATURE_OK, "digests SIGNATURES NOT OK", 1)
    tree["headers"].write_text(text)
    refused(rpmlock, tree, "SIGNATURES NOT OK")


def test_another_package_under_a_locked_name_is_refused(rpmlock, tree):
    text = tree["headers"].read_text().replace("\taudit\t0\t4.1.2", "\tevil\t0\t4.1.2", 1)
    tree["headers"].write_text(text)
    refused(rpmlock, tree, "header says evil")


def test_an_unchecked_rpm_is_refused(rpmlock, tree):
    lines = tree["headers"].read_text().splitlines(keepends=True)
    tree["headers"].write_text("".join(lines[1:]))
    refused(rpmlock, tree, "not checked")


def test_without_headers_only_checksums_are_claimed(rpmlock, tree):
    assert verify(rpmlock, tree, headers=False) == 3


# --- the lock file itself ---------------------------------------------------------------


def test_the_lock_matches_its_inputs(rpmlock, tree):
    rpmlock.check_lock(tree["lock"], INPUTS, BASE_LOCK)


def test_a_stale_lock_is_refused(rpmlock, tree):
    with pytest.raises(rpmlock.InputError, match="stale"):
        rpmlock.check_lock(tree["lock"], INPUTS + b"  - firewalld\n", BASE_LOCK)


def test_a_lock_for_another_base_is_refused(rpmlock, tree):
    other = BASE_LOCK.replace("a" * 64, "c" * 64)
    with pytest.raises(rpmlock.InputError, match="regenerate"):
        rpmlock.check_lock(tree["lock"], INPUTS, other)


@pytest.mark.parametrize(
    "cache",
    [
        "unpublished",
        "ghcr.io/ben10-games/aegis-os/rpm-inputs:latest",
        "ghcr.io/someone-else/rpm-inputs@sha256:" + "b" * 64,
    ],
)
def test_the_cache_must_be_ours_and_pinned_by_digest(rpmlock, tree, cache):
    tree["lock"].cache = cache
    with pytest.raises(rpmlock.InputError, match="cache"):
        rpmlock.check_lock(tree["lock"], INPUTS, BASE_LOCK)


def test_a_requested_package_missing_from_the_lock_is_refused(rpmlock, tree):
    tree["lock"].packages = [p for p in tree["lock"].packages if p.name != "audit"]
    with pytest.raises(rpmlock.InputError, match="'audit' requested for base"):
        rpmlock.check_lock(tree["lock"], INPUTS, BASE_LOCK)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("sha256: ", "sha256: 0"),  # not 64 hex digits
        ("repo: updates", "repo: updates, gpgcheck: 0"),  # unknown field
        ('evr: "4.1.2-1.fc45"', "evr: 4.1.2-1.fc45"),  # unquoted
        ("lockfileVersion: 1", "lockfileVersion: 2"),
        ('cache: "', 'cache: "x" #'),
        ("packages:", "packages: []"),
    ],
)
def test_malformed_lock_lines_are_refused(rpmlock, tree, old, new):
    text = tree["lock"].text()
    assert old in text
    with pytest.raises(rpmlock.InputError):
        rpmlock.parse_lock(text.replace(old, new, 1))


def test_an_unsorted_lock_is_refused(rpmlock, tree):
    lines = tree["lock"].text().splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith("  - "))
    lines[first], lines[first + 1] = lines[first + 1], lines[first]
    with pytest.raises(rpmlock.InputError, match="sorted"):
        rpmlock.parse_lock("\n".join(lines) + "\n")


def test_a_location_naming_another_package_is_refused(rpmlock, tree):
    text = tree["lock"].text().replace("Packages/a/audit-4.1.2", "Packages/a/audit-9.9.9", 1)
    with pytest.raises(rpmlock.InputError, match="does not name this package"):
        rpmlock.parse_lock(text)


@pytest.mark.parametrize(
    "text",
    [
        b"base:\n  - audit\nbase:\n  - firewalld\n",
        b"base:\n  - audit\n  - audit\n",
        b"base:\n",
        b"  - audit\n",
        b"base:\n  - audit; rm -rf /\n",
        b"base:\n  - $(id)\n",
    ],
)
def test_malformed_inputs_are_refused(rpmlock, text):
    with pytest.raises(rpmlock.InputError):
        rpmlock.parse_inputs(text.decode())


def test_build_lock_from_resolver_output(rpmlock, tmp_path):
    data = b"rpm"
    sha = hashlib.sha256(data).hexdigest()
    metadata = tmp_path / "metadata.tsv"
    metadata.write_text(
        f"base\taudit\t0\t4.1.2\t1.fc45\tx86_64\t{sha}\t3\taudit-4.1.2-1.fc45.x86_64.rpm\n"
        f"dev-policy\tselinux-policy-devel\t0\t45.24\t1.fc45\tnoarch\t{sha}\t3\t"
        "selinux-policy-devel-45.24-1.fc45.noarch.rpm\n"
    )
    repos = tmp_path / "repos.tsv"
    repos.write_text(
        "audit\t0\t4.1.2\t1.fc45\tx86_64\tupdates\tPackages/a/audit-4.1.2-1.fc45.x86_64.rpm\n"
        "selinux-policy-devel\t0\t45.24\t1.fc45\tnoarch\tfedora\t"
        "Packages/s/selinux-policy-devel-45.24-1.fc45.noarch.rpm\n"
    )
    lock = rpmlock.build_lock(metadata, repos, BASE, INPUTS)
    assert [p.name for p in lock.packages] == ["audit", "selinux-policy-devel"]
    assert lock.cache == rpmlock.UNPUBLISHED
    assert rpmlock.parse_lock(lock.text()) == lock


def test_build_lock_refuses_a_package_no_repository_offers(rpmlock, tmp_path):
    metadata = tmp_path / "metadata.tsv"
    metadata.write_text(
        f"base\taudit\t0\t4.1.2\t1.fc45\tx86_64\t{'0' * 64}\t3\taudit-4.1.2-1.fc45.x86_64.rpm\n"
    )
    repos = tmp_path / "repos.tsv"
    repos.write_text("")
    with pytest.raises(rpmlock.InputError, match="no repository offers"):
        rpmlock.build_lock(metadata, repos, BASE, INPUTS)


def test_the_command_line_reports_input_errors(rpmlock, tree, tmp_path, capsys):
    lock_path = tmp_path / "lock.yaml"
    lock_path.write_text(tree["lock"].text())
    (tree["dir"] / tree["packages"][0].path).unlink()
    status = rpmlock.main(["verify", "--lock", str(lock_path), "--dir", str(tree["dir"])])
    assert status == 1
    assert "INPUT ERROR:" in capsys.readouterr().err


def test_the_repository_inputs_parse(rpmlock, root):
    sets = rpmlock.parse_inputs((root / "image/packages/rpms.in.yaml").read_text())
    assert set(sets) == {"base", "dev", "dev-policy", "builder"}

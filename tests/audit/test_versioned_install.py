"""Fixed-version installer and release-pin regression tests."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


def _read(repo_root: Path, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )


def _installer_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "fixture-repository"
    (repository / "skills" / "ads" / "references").mkdir(parents=True)
    (repository / "skills" / "ads-google-app" / "references").mkdir(parents=True)
    (repository / "agents").mkdir()
    (repository / "scripts").mkdir()
    (repository / "skills" / "ads" / "SKILL.md").write_text(
        "---\nname: ads\ndescription: fixture\n---\n", encoding="utf-8"
    )
    (repository / "skills" / "ads" / "references" / "fixture.md").write_text(
        "fixture\n", encoding="utf-8"
    )
    (repository / "skills" / "ads-google-app" / "SKILL.md").write_text(
        "---\nname: ads-google-app\ndescription: fixture\n---\n", encoding="utf-8"
    )
    (
        repository / "skills" / "ads-google-app" / "references" / "agent-workflow.md"
    ).write_text("natural-language contract\n", encoding="utf-8")
    (
        repository / "skills" / "ads-google-app" / "references" / "private.txt"
    ).write_text("must not be installed\n", encoding="utf-8")
    (repository / "agents" / "fixture.md").write_text("fixture\n", encoding="utf-8")
    (repository / "scripts" / "fixture.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repository / "requirements.txt").write_text("", encoding="utf-8")
    (repository / "VERSION").write_text("1.2.3\n", encoding="utf-8")

    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "Installer Test")
    _git(repository, "config", "user.email", "installer-test@example.invalid")
    _git(repository, "add", ".")
    _git(repository, "commit", "-qm", "tagged fixture")
    _git(repository, "tag", "v1.2.3")

    (repository / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    _git(repository, "add", "VERSION")
    _git(repository, "commit", "-qm", "development fixture")
    return repository


def _run_unix_installer(
    repo_root: Path,
    fixture_repository: Path,
    destination: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(destination / "home"),
            "CODEX_ADS_REPO_URL": str(fixture_repository),
        }
    )
    skill_dir = destination / "skills with spaces"
    agent_dir = destination / "agents with spaces"
    return subprocess.run(
        [
            shutil.which("bash") or "bash",
            str(repo_root / "install.sh"),
            "--target=cursor",
            f"--skill-dir={skill_dir}",
            f"--agent-dir={agent_dir}",
            *extra_args,
        ],
        cwd=repo_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_windows_installer(
    repo_root: Path,
    fixture_repository: Path,
    destination: Path,
    ref: str,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    temporary = destination / "temp"
    temporary.mkdir(parents=True)
    environment = os.environ.copy()
    environment.update(
        {
            "CODEX_ADS_REPO_URL": str(fixture_repository),
            "TEMP": str(temporary),
            "USERPROFILE": str(destination / "home"),
        }
    )
    skill_dir = destination / "skills with spaces"
    agent_dir = destination / "agents with spaces"
    completed = subprocess.run(
        [
            shutil.which("pwsh") or "pwsh",
            "-NoProfile",
            "-File",
            str(repo_root / "install.ps1"),
            "-Target",
            "cursor",
            "-SkillDir",
            str(skill_dir),
            "-AgentDir",
            str(agent_dir),
            "-Ref",
            ref,
        ],
        cwd=repo_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed, skill_dir


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None or shutil.which("git") is None,
    reason="the Unix installer smoke test requires a Unix host, bash, and git",
)
def test_unix_installer_pins_a_tag_and_preserves_default_clone_behavior(
    repo_root: Path, tmp_path: Path
) -> None:
    fixture_repository = _installer_fixture(tmp_path)

    pinned = _run_unix_installer(
        repo_root, fixture_repository, tmp_path / "pinned", "--ref=v1.2.3"
    )
    development = _run_unix_installer(
        repo_root, fixture_repository, tmp_path / "development"
    )

    assert pinned.returncode == 0, pinned.stdout + pinned.stderr
    assert development.returncode == 0, development.stdout + development.stderr
    assert (tmp_path / "pinned" / "skills with spaces" / "ads" / "VERSION").read_text(
        encoding="utf-8"
    ) == "1.2.3\n"
    assert (
        tmp_path / "development" / "skills with spaces" / "ads" / "VERSION"
    ).read_text(encoding="utf-8") == "9.9.9\n"
    for channel in ["pinned", "development"]:
        installed_reference = (
            tmp_path
            / channel
            / "skills with spaces"
            / "ads-google-app"
            / "references"
            / "agent-workflow.md"
        )
        assert installed_reference.read_text(encoding="utf-8") == (
            "natural-language contract\n"
        )
        assert not installed_reference.with_name("private.txt").exists()


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None or shutil.which("git") is None,
    reason="the Unix installer test requires a Unix host, bash, and git",
)
def test_unix_installer_uses_the_tag_when_a_branch_has_the_same_name(
    repo_root: Path, tmp_path: Path
) -> None:
    fixture_repository = _installer_fixture(tmp_path)
    _git(fixture_repository, "branch", "v1.2.3")

    completed = _run_unix_installer(
        repo_root, fixture_repository, tmp_path / "ambiguous", "--ref=v1.2.3"
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (
        tmp_path / "ambiguous" / "skills with spaces" / "ads" / "VERSION"
    ).read_text(encoding="utf-8") == "1.2.3\n"


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None,
    reason="the Unix installer test requires a Unix host and bash",
)
@pytest.mark.parametrize(
    "invalid_ref",
    ["1.2.3", "v1.2", "v1.2.3-beta", "main", "v1.2.3/other", ""],
)
def test_unix_installer_rejects_non_release_refs(
    repo_root: Path, tmp_path: Path, invalid_ref: str
) -> None:
    completed = subprocess.run(
        ["bash", str(repo_root / "install.sh"), f"--ref={invalid_ref}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "Invalid --ref" in completed.stderr


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None or shutil.which("git") is None,
    reason="the Unix installer test requires a Unix host, bash, and git",
)
def test_unix_installer_rejects_a_version_shaped_branch(
    repo_root: Path, tmp_path: Path
) -> None:
    fixture_repository = _installer_fixture(tmp_path)
    _git(fixture_repository, "branch", "v2.0.0")

    completed = _run_unix_installer(
        repo_root, fixture_repository, tmp_path / "branch", "--ref=v2.0.0"
    )

    assert completed.returncode == 1
    assert "does not resolve to a release tag" in completed.stderr


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh is required")
def test_windows_installer_accepts_an_exact_release_ref(
    repo_root: Path, tmp_path: Path
) -> None:
    fixture_repository = _installer_fixture(tmp_path)
    _git(fixture_repository, "branch", "v1.2.3")
    destination = tmp_path / "windows pinned"
    completed, skill_dir = _run_windows_installer(
        repo_root, fixture_repository, destination, "v1.2.3"
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (skill_dir / "ads" / "VERSION").read_text(encoding="utf-8") == "1.2.3\n"
    installed_reference = (
        skill_dir / "ads-google-app" / "references" / "agent-workflow.md"
    )
    assert installed_reference.read_text(encoding="utf-8") == (
        "natural-language contract\n"
    )
    assert not installed_reference.with_name("private.txt").exists()


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh is required")
def test_windows_installer_rejects_a_version_shaped_branch_without_a_tag(
    repo_root: Path, tmp_path: Path
) -> None:
    fixture_repository = _installer_fixture(tmp_path)
    _git(fixture_repository, "branch", "v2.0.0")

    completed, _skill_dir = _run_windows_installer(
        repo_root, fixture_repository, tmp_path / "windows branch", "v2.0.0"
    )

    assert completed.returncode != 0
    assert "does not resolve to a release tag" in completed.stdout + completed.stderr


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh is required")
@pytest.mark.parametrize("invalid_ref", ["1.2.3", "v1.2", "v1.2.3-beta", "main"])
def test_windows_installer_rejects_non_release_refs(
    repo_root: Path, invalid_ref: str
) -> None:
    completed = subprocess.run(
        [
            shutil.which("pwsh") or "pwsh",
            "-NoProfile",
            "-File",
            str(repo_root / "install.ps1"),
            "-Ref",
            invalid_ref,
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0


def test_unix_and_windows_installers_share_the_release_ref_contract(
    repo_root: Path,
) -> None:
    shell = _read(repo_root, "install.sh")
    powershell = _read(repo_root, "install.ps1")
    release_docs = _read(repo_root, "docs/releasing.md")

    assert "^v[0-9]+\\.[0-9]+\\.[0-9]+$" in shell
    assert "[ValidatePattern('^v[0-9]+\\.[0-9]+\\.[0-9]+$')]" in powershell
    assert '"refs/tags/${REPO_REF}:refs/tags/${REPO_REF}"' in shell
    assert '"refs/tags/${Ref}:refs/tags/${Ref}"' in powershell
    assert "checkout --quiet --detach" in shell
    assert "checkout --quiet --detach" in powershell
    assert "HEAD_COMMIT" in shell and "TAG_COMMIT" in shell
    assert "$HeadCommit" in powershell and "$TagCommit" in powershell
    assert "show-ref --verify --quiet" in shell
    assert '"refs/tags/${REPO_REF}"' in shell
    assert 'show-ref --verify --quiet "refs/tags/$Ref"' in powershell
    assert 'cp "${TEMP_DIR}/codex-ads/VERSION" "${SKILL_DIR}/VERSION"' in shell
    assert 'Copy-Item (Join-Path $SourceDir "VERSION")' in powershell
    assert "--ref=vX.Y.Z" in release_docs
    assert "-Ref vX.Y.Z" in release_docs

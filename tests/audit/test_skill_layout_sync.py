"""Regression tests for the canonical Ads router mirror."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from sync_skill_layout import (  # noqa: E402
    LayoutError,
    inspect_layout,
    synchronize_layout,
)


def _layout(root: Path) -> tuple[Path, Path]:
    canonical = root / "skills" / "ads"
    mirror = root / "ads"
    (canonical / "references").mkdir(parents=True)
    (canonical / "SKILL.md").write_text("canonical router\n", encoding="utf-8")
    (canonical / "references" / "one.md").write_text("one\n", encoding="utf-8")
    return canonical, mirror


def test_inspection_reports_missing_drift_and_extra_entries(tmp_path: Path) -> None:
    canonical, mirror = _layout(tmp_path)
    (mirror / "references" / "extra").mkdir(parents=True)
    (mirror / "SKILL.md").write_text("drifted router\n", encoding="utf-8")
    (mirror / "references" / "extra" / "old.md").write_text("old\n", encoding="utf-8")

    state = inspect_layout(canonical, mirror)

    assert state.missing_files == ("references/one.md",)
    assert state.drifted_files == ("SKILL.md",)
    assert state.extra_files == ("references/extra/old.md",)
    assert state.extra_directories == ("references/extra",)
    assert not state.clean


def test_write_makes_the_legacy_tree_an_exact_mirror(tmp_path: Path) -> None:
    canonical, mirror = _layout(tmp_path)
    (mirror / "references").mkdir(parents=True)
    (mirror / "SKILL.md").write_text("drifted\n", encoding="utf-8")
    (mirror / "obsolete.md").write_text("obsolete\n", encoding="utf-8")

    final_state = synchronize_layout(canonical, mirror)

    assert final_state.clean
    assert (mirror / "SKILL.md").read_bytes() == (canonical / "SKILL.md").read_bytes()
    assert (mirror / "references" / "one.md").read_bytes() == (
        canonical / "references" / "one.md"
    ).read_bytes()
    assert not (mirror / "obsolete.md").exists()


def test_write_refuses_symbolic_links(tmp_path: Path) -> None:
    canonical, mirror = _layout(tmp_path)
    mirror.mkdir()
    try:
        os.symlink(canonical / "SKILL.md", mirror / "SKILL.md")
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable in this environment")

    state = inspect_layout(canonical, mirror)
    assert state.unsafe_entries == ("mirror:SKILL.md",)
    with pytest.raises(LayoutError, match="unsafe entries"):
        synchronize_layout(canonical, mirror)


def test_cli_check_and_write_have_stable_exit_codes(tmp_path: Path) -> None:
    canonical, mirror = _layout(tmp_path)
    script = SCRIPTS_DIR / "sync_skill_layout.py"

    check_before = subprocess.run(
        [sys.executable, str(script), "--check", "--repo-root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    write = subprocess.run(
        [sys.executable, str(script), "--write", "--repo-root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    check_after = subprocess.run(
        [sys.executable, str(script), "--check", "--repo-root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert canonical.is_dir() and mirror.is_dir()
    assert check_before.returncode == 1
    assert write.returncode == 0
    assert check_after.returncode == 0
    assert "synchronized" in check_after.stdout


def test_repository_router_is_currently_synchronized(repo_root: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "sync_skill_layout.py"), "--check"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr

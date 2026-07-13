#!/usr/bin/env python3
"""Check or synchronize the canonical Ads router into its legacy mirror.

``skills/ads`` is the canonical plugin layout. ``ads`` remains available for
legacy/raw installs and must be a byte-for-byte mirror. The writer refuses to
operate when either tree contains symbolic links or special filesystem
entries, so a synchronization cannot escape the two repository directories.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class LayoutError(RuntimeError):
    """Raised when the router layout cannot be inspected or synchronized safely."""


@dataclass(frozen=True)
class _Inventory:
    files: dict[str, Path]
    directories: frozenset[str]
    unsafe_entries: tuple[str, ...]


@dataclass(frozen=True)
class LayoutState:
    """Difference between the canonical and mirrored router trees."""

    missing_files: tuple[str, ...]
    drifted_files: tuple[str, ...]
    extra_files: tuple[str, ...]
    missing_directories: tuple[str, ...]
    extra_directories: tuple[str, ...]
    unsafe_entries: tuple[str, ...]

    @property
    def clean(self) -> bool:
        return not any(
            (
                self.missing_files,
                self.drifted_files,
                self.extra_files,
                self.missing_directories,
                self.extra_directories,
                self.unsafe_entries,
            )
        )


def _inventory(root: Path, *, allow_missing: bool, label: str) -> _Inventory:
    if root.is_symlink():
        return _Inventory({}, frozenset(), (f"{label}:.",))
    if not root.exists():
        if allow_missing:
            return _Inventory({}, frozenset(), ())
        raise LayoutError(f"{label} directory is missing")
    if not root.is_dir():
        raise LayoutError(f"{label} path is not a directory")

    files: dict[str, Path] = {}
    directories: set[str] = set()
    unsafe: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            unsafe.append(f"{label}:{relative}")
        elif path.is_file():
            files[relative] = path
        elif path.is_dir():
            directories.add(relative)
        else:
            unsafe.append(f"{label}:{relative}")
    return _Inventory(files, frozenset(directories), tuple(unsafe))


def inspect_layout(canonical: Path, mirror: Path) -> LayoutState:
    """Return a complete, non-mutating comparison of the two router trees."""

    canonical_inventory = _inventory(canonical, allow_missing=False, label="canonical")
    if "SKILL.md" not in canonical_inventory.files:
        raise LayoutError("canonical router is missing SKILL.md")
    if "references" not in canonical_inventory.directories:
        raise LayoutError("canonical router is missing references/")

    mirror_inventory = _inventory(mirror, allow_missing=True, label="mirror")
    canonical_files = set(canonical_inventory.files)
    mirror_files = set(mirror_inventory.files)
    shared_files = canonical_files & mirror_files
    drifted = sorted(
        relative
        for relative in shared_files
        if canonical_inventory.files[relative].read_bytes()
        != mirror_inventory.files[relative].read_bytes()
    )

    return LayoutState(
        missing_files=tuple(sorted(canonical_files - mirror_files)),
        drifted_files=tuple(drifted),
        extra_files=tuple(sorted(mirror_files - canonical_files)),
        missing_directories=tuple(
            sorted(canonical_inventory.directories - mirror_inventory.directories)
        ),
        extra_directories=tuple(
            sorted(mirror_inventory.directories - canonical_inventory.directories)
        ),
        unsafe_entries=tuple(
            sorted(canonical_inventory.unsafe_entries + mirror_inventory.unsafe_entries)
        ),
    )


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        descriptor, temporary_path = tempfile.mkstemp(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
        )
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(source.read_bytes())
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, source.stat().st_mode & 0o777)
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def synchronize_layout(canonical: Path, mirror: Path) -> LayoutState:
    """Make ``mirror`` exactly match ``canonical`` and return the final state."""

    state = inspect_layout(canonical, mirror)
    if state.unsafe_entries:
        entries = ", ".join(state.unsafe_entries)
        raise LayoutError(f"refusing to write a layout with unsafe entries: {entries}")

    mirror.mkdir(parents=True, exist_ok=True)

    # Remove files before directories so file/directory type conflicts can be
    # repaired without following or recursively deleting unknown paths.
    for relative in sorted(
        state.extra_files, key=lambda item: item.count("/"), reverse=True
    ):
        (mirror / relative).unlink()
    for relative in sorted(
        state.extra_directories, key=lambda item: item.count("/"), reverse=True
    ):
        (mirror / relative).rmdir()

    for relative in state.missing_directories:
        (mirror / relative).mkdir(parents=True, exist_ok=True)
    for relative in (*state.missing_files, *state.drifted_files):
        _atomic_copy(canonical / relative, mirror / relative)

    final_state = inspect_layout(canonical, mirror)
    if not final_state.clean:
        raise LayoutError("router layout remained inconsistent after synchronization")
    return final_state


def _format_state(state: LayoutState) -> str:
    if state.clean:
        return "skill layout is synchronized"
    groups = (
        ("missing file", state.missing_files),
        ("drifted file", state.drifted_files),
        ("extra file", state.extra_files),
        ("missing directory", state.missing_directories),
        ("extra directory", state.extra_directories),
        ("unsafe entry", state.unsafe_entries),
    )
    lines = ["skill layout is not synchronized:"]
    for label, entries in groups:
        lines.extend(f"- {label}: {entry}" for entry in entries)
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check or update the legacy ads/ mirror from skills/ads/"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="report drift without writing"
    )
    mode.add_argument(
        "--write", action="store_true", help="safely synchronize the mirror"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.repo_root.expanduser().resolve()
    canonical = root / "skills" / "ads"
    mirror = root / "ads"
    try:
        state = inspect_layout(canonical, mirror)
        if args.check:
            print(_format_state(state))
            return 0 if state.clean else 1
        if state.clean:
            print("skill layout is already synchronized")
            return 0
        synchronize_layout(canonical, mirror)
        print("skill layout synchronized from skills/ads to ads")
        return 0
    except (LayoutError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

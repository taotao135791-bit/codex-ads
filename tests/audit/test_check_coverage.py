"""Catalog ↔ reference-file bidirectional coverage tests.

Two invariants:

1. **No orphans in the catalog** — every check ID in
   ``tests/fixtures/check-catalog.yaml`` must appear in its platform's
   audit reference file under ``ads/references/``.

2. **No untracked rows in the references** — every check ID with a table
   row in those reference files must appear in the catalog.

A drift in either direction fails the build, forcing the maintainer to
update the catalog whenever a new check is added or an old one is removed.
"""

from __future__ import annotations

import re


_ID_ROW_RE = re.compile(r"^\|\s*([A-Z]+(?:-[A-Z]+)?[0-9]+)\s*\|", re.MULTILINE)


def _ids_in_reference(path) -> set[str]:
    """Extract every check ID from a markdown audit reference's table rows."""
    text = path.read_text(encoding="utf-8")
    return set(_ID_ROW_RE.findall(text))


def test_catalog_total_counts_match_reference_headers(check_catalog, repo_root):
    """The ``total_checks`` field per platform should equal the number of IDs
    listed in that platform's ``check_ids`` array. Caught early because it's a
    fast deterministic check."""
    for platform_name, platform in check_catalog["platforms"].items():
        listed = len(platform["check_ids"])
        declared = platform["total_checks"]
        assert listed == declared, (
            f"{platform_name}: catalog declares {declared} total_checks but lists {listed} IDs"
        )


def test_every_catalog_id_exists_in_reference(check_catalog, repo_root):
    """For each platform, every catalog check_id must appear as a table row
    in the corresponding audit reference file."""
    failures: list[str] = []
    for platform_name, platform in check_catalog["platforms"].items():
        ref_path = repo_root / platform["reference"]
        assert ref_path.exists(), (
            f"{platform_name}: reference file missing at {ref_path}"
        )
        present = _ids_in_reference(ref_path)
        for check_id in platform["check_ids"]:
            if check_id not in present:
                failures.append(
                    f"{platform_name}: {check_id} in catalog but not in {platform['reference']}"
                )
    assert not failures, "Orphan catalog entries:\n  " + "\n  ".join(failures)


def test_every_reference_row_appears_in_catalog(check_catalog, repo_root):
    """Reverse direction: every table row in an audit reference must have a
    catalog entry. Catches the case where someone adds a new check to the
    reference but forgets to update the catalog."""
    failures: list[str] = []
    for platform_name, platform in check_catalog["platforms"].items():
        ref_path = repo_root / platform["reference"]
        present = _ids_in_reference(ref_path)
        catalog_set = set(platform["check_ids"])
        untracked = present - catalog_set
        if untracked:
            failures.append(
                f"{platform_name}: {sorted(untracked)} in reference but not catalog"
            )
    assert not failures, "Untracked reference rows:\n  " + "\n  ".join(failures)


def test_total_check_count_is_at_least_209(check_catalog):
    """Sanity: codex-ads's README headline is '250+ checks'. The 5 platform
    catalogs alone account for 209; cross-platform (creative, landing, budget,
    compliance) make up the rest. This test pins the baseline so a future
    regression that drops checks fires immediately."""
    total = sum(len(p["check_ids"]) for p in check_catalog["platforms"].values())
    assert total >= 209, f"Platform catalogs total {total}; baseline is 209"

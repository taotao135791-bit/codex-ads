"""Architecture boundaries that keep the historical entry point compatible."""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import uac_experiment  # noqa: E402
from codex_ads import uac  # noqa: E402


def test_legacy_entry_is_a_small_compatibility_layer(repo_root):
    entry = repo_root / "scripts" / "uac_experiment.py"
    text = entry.read_text(encoding="utf-8")

    assert len(text.splitlines()) < 100
    assert "from codex_ads.uac import" in text
    assert "def analyze_case" not in text
    assert "def validate_ledger" not in text


def test_legacy_public_symbols_are_the_same_internal_objects():
    for name in (
        "ContractError",
        "analyze_case",
        "review_experiment",
        "validate_experiment",
        "validate_ledger",
        "validate_analysis",
        "render_markdown",
        "migrate_ledger",
        "run_doctor",
        "normalize_uac_input",
        "derive_signals",
        "recommend_numeric",
        "replay_path",
    ):
        assert getattr(uac_experiment, name) is getattr(uac, name)


def test_report_rendering_does_not_mutate_structured_analysis(repo_root):
    case = yaml.safe_load(
        (
            repo_root
            / "skills"
            / "ads-google-app"
            / "assets"
            / "UAC-INPUT.example.yaml"
        ).read_text(encoding="utf-8")
    )
    result = uac.analyze_case(case)
    before = deepcopy(result)

    rendered = uac.render_markdown(result)

    assert result == before
    assert "# UAC Experiment Loop Report" in rendered

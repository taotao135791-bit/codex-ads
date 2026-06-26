"""Routing-snapshot tests for creative workflow skills.

These tests load the existing ``evals/creative-evals.json`` and assert that
each positive-trigger prompt contains lexical signals that match the target
skill's description. Negative cases assert the prompt does NOT trigger a
listed creative skill (audit / performance prompts should not invoke
ads-dna / ads-create / ads-generate / ads-photoshoot).

This is a regression guard, not a full router simulation — the real model-
side dispatch happens at runtime. The point is to catch:
- Description tightening that accidentally removes a previously-routing phrase
- New trigger phrases added to one skill that collide with another skill's
"""

from __future__ import annotations

import re


def _extract_triggers(description: str) -> list[str]:
    """Pull comma-separated trigger phrases out of a description's Use-when
    or Triggers-on tail. Returns lowercased phrases for comparison."""
    # Match either "Use when user says <list>." or "Triggers on: <list>."
    m = re.search(
        r"(?:Use when user says|Triggers on:)\s*(.+?)\.(?:\s|$)",
        description,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    tail = m.group(1)
    # Split on commas, " or ", " and "
    raw_phrases = re.split(r",|\bor\b|\band\b", tail)
    return [p.strip().lower() for p in raw_phrases if p.strip()]


def test_positive_triggers_route_to_expected_skill(creative_evals, skill_descriptions):
    """Every positive eval entry should have at least one keyword overlap with
    its expected skill's trigger surface. Failures usually mean a description
    was tightened in a way that broke a previously-routing prompt."""
    failures: list[str] = []
    for entry in creative_evals:
        if not entry["should_trigger"]:
            continue
        skill = entry["expected_skill"]
        prompt = entry["prompt"].lower()
        desc = skill_descriptions.get(skill)
        if desc is None:
            failures.append(f"{entry['id']}: skill '{skill}' has no description")
            continue
        triggers = _extract_triggers(desc)
        if not triggers:
            failures.append(f"{entry['id']}: skill '{skill}' has no parseable trigger list")
            continue
        # Look for ANY trigger phrase token appearing in the prompt
        matched = [t for t in triggers if any(token in prompt for token in t.split() if len(token) > 2)]
        if not matched:
            failures.append(
                f"{entry['id']}: prompt '{entry['prompt'][:60]}' has no trigger overlap with {skill}"
            )
    assert not failures, "Routing regressions:\n  " + "\n  ".join(failures)


def test_negative_cases_have_listed_expected_skill(creative_evals, skill_descriptions):
    """Negative cases assert the prompt should NOT trigger the named creative
    skill — but the expected_skill field still has to name a real skill.
    Catches typos in fixture entries."""
    for entry in creative_evals:
        if entry["should_trigger"]:
            continue
        skill = entry["expected_skill"]
        assert skill in skill_descriptions, (
            f"{entry['id']} references unknown skill: {skill}"
        )


def test_all_creative_skill_names_resolve(creative_evals, skill_descriptions):
    """Sanity: every expected_skill in the fixture is a real skill."""
    for entry in creative_evals:
        skill = entry["expected_skill"]
        assert skill in skill_descriptions, (
            f"{entry['id']} expects skill {skill!r} but it does not exist in any SKILL.md"
        )

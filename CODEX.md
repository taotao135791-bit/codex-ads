# Codex Ads Project Notes

Codex Ads is a local skill bundle for paid media audits, planning, creative review, PPC calculators, attribution checks, and PDF reporting.

## Layout

- `ads/SKILL.md`: main `/ads` orchestrator skill.
- `skills/ads-*`: focused sub-skills for platforms and workflows.
- `skills/ads-google-app`: UAC feasibility, structured analysis, and local
  experiment-ledger contracts.
- `agents/*.md`: reusable audit and creative agents.
- `ads/references/*.md`: scoring, platform specs, compliance, benchmarks, and implementation references.
- `scripts/*.py`: optional local utilities for page fetches, screenshots, landing-page analysis, image generation, and PDF reports.
- `scripts/uac_experiment.py`: deterministic UAC fixture replay, ledger review,
  structured analysis, and Markdown report helper.
- `tests/`: pytest coverage for routing, scoring, check catalogs, and URL safety.

## Codex Runtime

Default install target is Codex:

```bash
bash install.sh
```

This installs skills to `~/.codex/skills` and agents to `~/.codex/agents`.

## Development

Run the test suite with:

```bash
pytest -q
ruff check scripts tests
```

# Private replay workspace

`workspaces/<project>/replays/` is the preferred long-term home for real account
replays and is ignored by Git. This legacy `replays/` directory also remains
ignored for compatibility. Store real cases only after removing unnecessary
identifiers and limiting local file permissions. Never move a real case into
`examples/replays/`.

Keep six immutable stages per case so a later review can distinguish what the
system recommended, what a human decided, and what was actually executed:

```text
workspaces/<project>/replays/<replay-id>/
  snapshot-before.yaml
  system-recommendation.yaml
  human-decision.yaml
  actual-action.yaml
  snapshot-after.yaml
  evaluation.yaml
```

The six stages have separate ownership:

1. `snapshot-before.yaml` freezes only information available before action.
2. `system-recommendation.yaml` freezes the exact codex-ads version,
   feasibility, data gaps, proposed variable, and protected variables.
3. `human-decision.yaml` records the human judgment and whether the system
   recommendation was accepted.
4. `actual-action.yaml` records approval role, execution time, actual changes,
   deviations, concurrent changes, and rollback.
5. `snapshot-after.yaml` records observation length, maturity, backend evidence,
   finite outcome metrics, and confounders.
6. `evaluation.yaml` records workflow usefulness and whether the result is
   conclusive, attributable, positive, negative, or insufficient.

Use `examples/replays/example-anonymized/` as the public six-stage field
contract. The replay CLI prefers these six files. Existing five-file cases that
combine the system recommendation and human judgment in
`decision-at-the-time.yaml` remain readable, so old private cases do not need an
immediate rewrite.

`causal_claim` must remain `false` because replay is retrospective workflow
evidence. Contradictory records such as `executed: false` with changed variables
are rejected rather than guessed. Positive or negative conclusions require at
least one finite numeric after-metric and an `observation_days` value that
reaches the original `experiment_policy.minimum_days`; labels cannot override
those evidence gates. Confounded experiments, deviations, and explicitly
rejected system recommendations are counted outside the attributable effect
denominator; they never become system wins or losses.

Never store client names, account/customer/campaign IDs, personal contact
details, payment information, tokens, dashboard cookies, signed URLs, or raw
exports that are not needed for evaluation. Prefer anonymous stable labels and
coarsened values. Repository ignore rules reduce accidental commits but do not
replace access control, encryption, backups, or a manual review before sharing.

Run a local case with:

```bash
python3 scripts/uac_experiment.py replay \
  workspaces/<project>/replays/<replay-id> --json
```

Replay output is diagnostic evidence for improving this project. It is not a
causal proof, a platform-wide benchmark, or permission to change an account.
If a human did not execute a recommendation, that case is neither a system win
nor a system loss. Small samples and positive experiment rates are not evidence
of platform-level incrementality.

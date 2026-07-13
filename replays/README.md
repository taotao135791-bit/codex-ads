# Private replay workspace

Everything in this directory except this README is ignored by Git. Store real
account replay cases here only after removing unnecessary identifiers and
limiting local file permissions. Do not move private cases into
`examples/replays/`.

Create one directory per case with these five files:

```text
replays/<private-case>/
  snapshot-before.yaml
  decision-at-the-time.yaml
  actual-action.yaml
  snapshot-after.yaml
  evaluation.yaml
```

Use `examples/replays/example-anonymized/` as the field contract. Each case must
record the original snapshot time and structured UAC input; human judgment,
the codex-ads version/confidence/data gaps; approval role, execution time and
actual/concurrent changes; mature after-metrics, backend availability and
confounders; and a human evaluation. `causal_claim` must remain `false` because
replay is retrospective workflow evidence. Contradictory records such as
`executed: false` with changed variables are rejected rather than guessed.
Positive or negative conclusions also require at least one finite numeric
after-metric and an `observation_days` value that reaches the original
`experiment_policy.minimum_days`; labels cannot override those evidence gates.

Never store client names, account/customer/campaign IDs, personal contact
details, payment information, tokens, dashboard cookies, signed URLs, or raw
exports that are not needed for evaluation. Prefer anonymous stable labels and
coarsened values. Repository ignore rules reduce accidental commits but do not
replace access control, encryption, backups, or a manual review before sharing.

Run a local case with:

```bash
python3 scripts/uac_experiment.py replay replays/<private-case> --json
```

Replay output is diagnostic evidence for improving this project. It is not a
causal proof, a platform-wide benchmark, or permission to change an account.

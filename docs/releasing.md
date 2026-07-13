# Releasing Codex Ads

This checklist is the release contract for maintainers. A version is not a
release until its commit, annotated tag, and GitHub Release are all visible on
the remote repository.

## 1. Prepare

1. Work from a clean branch based on the current `origin/main`.
2. Update the root `VERSION`, plugin manifest, runtime version strings, and
   `CHANGELOG.md` together.
3. Confirm public fixtures and replay examples are anonymous. Never commit
   account names, account or campaign IDs, personal email addresses, payment
   data, access tokens, or private dashboard exports.
4. Run the repository privacy scan and inspect commit author/committer metadata.
5. Use a GitHub noreply address for release commits and tags.

## 2. Validate

Run from the repository root:

```bash
python3 -m pytest -q
ruff check .
ruff format --check .
python3 -m mypy
python3 scripts/uac_experiment.py --help
python3 scripts/uac_experiment.py doctor --json
python3 scripts/uac_experiment.py replay examples/replays/example-anonymized --json
python3 scripts/sync_skill_layout.py --check
python3 scripts/knowledge_doctor.py --json
python3 scripts/privacy_doctor.py --history --json
bash -n install.sh
git diff --check
```

Also verify the UAC example analysis, ledger validation/review, explicit schema
migration preview, report generation, and an installer smoke test. GitHub
Actions must be green on Ubuntu, macOS, and Windows for the minimum and newest
supported Python versions. Tests must not call an advertising API, private
account, paid model, or logged-in browser.

## 3. Tag and publish

Replace `X.Y.Z` with the exact value in `VERSION`:

```bash
git tag -s vX.Y.Z -m "codex-ads vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

If signed tags are unavailable, use an annotated tag and document that choice:

```bash
git tag -a vX.Y.Z -m "codex-ads vX.Y.Z"
```

Create a GitHub Release from that exact tag. Copy the relevant CHANGELOG entry,
state compatibility and migration behavior, and link to rollback instructions.
Do not call a draft or local tag a published release.

## 4. Verify the fixed version

On a clean temporary directory, install the tag rather than `main`:

```bash
curl -fsSL https://raw.githubusercontent.com/taotao135791-bit/codex-ads/vX.Y.Z/install.sh \
  | bash -s -- --ref=vX.Y.Z
```

Run the installed UAC helper with `--help` and `doctor --json`, then analyze the
bundled anonymous example. Confirm that the reported version equals the tag.

On Windows PowerShell, download the installer from the same tag and pass the
matching validated release ref:

```powershell
irm https://raw.githubusercontent.com/taotao135791-bit/codex-ads/vX.Y.Z/install.ps1 `
  -OutFile install.ps1
.\install.ps1 -Ref vX.Y.Z
```

## 5. Roll back

Installation rollback is non-destructive: reinstall a known-good tag with
`--ref=vX.Y.Z`, or with PowerShell `-Ref vX.Y.Z`, after confirming that tag is
published and known-good. Back up a project ledger before replacing tools.
Schema migration is explicit and should be written to a new output file first;
never downgrade or rewrite a user ledger implicitly.

If the release itself is bad, do not move or reuse its tag. Publish a new patch
version that reverts the faulty change, and explain the rollback in both the
CHANGELOG and GitHub Release notes.

## 6. Post-release checks

- Confirm the tag and GitHub Release resolve to the same commit.
- Confirm fixed-version install URLs work on Unix and Windows.
- Confirm `main` documentation labels it as the development channel.
- Confirm no secret, personal identity, or private replay data appears in the
  release diff or reachable Git history.

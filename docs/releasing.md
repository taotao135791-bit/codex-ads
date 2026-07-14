# Releasing Codex Ads

This checklist is the release contract for maintainers. A version is not a
release until its commit, annotated tag, and GitHub Release are all visible on
the remote repository. Preparing `VERSION` or a CHANGELOG entry does not publish
anything.

The required sequence is: (1) update every version source and CHANGELOG,
(2) run local tests/static checks/coverage, (3) pass the current-tree privacy
scan, (4) push or merge the untagged candidate to `main`, (5) wait for all
cross-platform CI jobs, (6) pass the full-history Release Privacy Gate,
(7) create the exact annotated or signed tag locally, (8) rerun the full-history
scan so tagger metadata and the tag message are inspected before upload,
(9) push the tag and wait for its automatic remote Release Privacy Gate,
(10) create the GitHub Release, and (11) verify fixed-version install and
rollback on clean Unix and Windows environments.

## 1. Prepare

1. Work from a clean branch based on the current `origin/main`.
2. Update the root `VERSION`, plugin manifest, report/runtime user-agent version
   strings, fixed-version documentation, anonymous replay version, and
   `CHANGELOG.md` together.
3. Confirm public fixtures and replay examples are anonymous. Never commit
   account names, account or campaign IDs, personal email addresses, payment
   data, access tokens, or private dashboard exports.
4. Run the repository privacy scan and inspect commit author/committer metadata.
5. Use the public GitHub handle as `user.name` and its matching GitHub noreply
   address as `user.email` for release commits and tags. The gate rejects a
   different display name even when the email itself is noreply, because that
   name may retain personal identity metadata.

## 2. Validate

Run from the repository root:

```bash
python3 -m pytest -q
ruff check .
ruff format --check .
python3 -m mypy scripts/codex_ads/uac
python3 -m pytest -q \
  --cov=codex_ads.uac \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=80
python3 scripts/uac_experiment.py --help
python3 scripts/uac_experiment.py decide --help
python3 scripts/uac_experiment.py decide \
  skills/ads-google-app/assets/UAC-QUICK-OPS.example.yaml
python3 scripts/uac_experiment.py decide \
  skills/ads-google-app/assets/UAC-QUICK-NUMERIC.example.yaml --json
python3 scripts/uac_experiment.py doctor --json
python3 scripts/uac_experiment.py replay examples/replays/example-anonymized --json
python3 scripts/sync_skill_layout.py --check
python3 scripts/knowledge_doctor.py --json
python3 scripts/privacy_doctor.py --json
bash -n install.sh
git diff --check
```

Also verify `init-workspace` in a temporary directory, the UAC example analysis,
ledger validation/review, explicit schema migration preview, report generation,
and both installer paths. Confirm the installed `ads-google-app` skill contains
`references/agent-workflow.md`. GitHub Actions must be green on Ubuntu, macOS,
and Windows for the minimum and newest supported Python versions. Tests must not
call an advertising API, private account, paid model, or logged-in browser.

Push or merge the candidate commit to `main` without a tag and wait for ordinary
CI to pass. Ordinary CI intentionally scans only the candidate tree. Before a
release, separately run the full-history command locally, then run the remote
workflow, which checks out with
`fetch-depth: 0`:

```bash
python3 scripts/privacy_doctor.py --history --json
gh workflow run release-gate.yml --ref main
```

Inspect the completed **Release Privacy Gate** run. It must pass. The equivalent
local command is `python3 scripts/privacy_doctor.py --history --json`, but a
local clone may not contain every remote ref. If either audit reports historical
identity, bytecode, workspace, credential, or account-identifier findings, stop:
do not create or push a tag. History rewriting and force-pushing require
separate explicit maintainer authorization and a fresh-clone verification.

### Current v1.9.2 candidate status

The 2026-07-14 audit reconfirmed legacy identity metadata (including display names),
historical Python bytecode, and token-shaped credential strings in reachable
history. That release block remains in force for the v1.9.2 candidate, which is
therefore intentionally
**not eligible for a tag or GitHub Release** until
that history is explicitly cleaned, force-pushed with authorization, audited
from a fresh full clone, and the Release Privacy Gate passes. A clean current
tree or green ordinary CI does not override this block.

## 3. Tag and publish

Only after the normal CI and Release Privacy Gate are green, replace `X.Y.Z`
with the exact value in `VERSION`:

```bash
git switch main
git pull --ff-only origin main
git tag -s vX.Y.Z -m "codex-ads vX.Y.Z"
```

If signed tags are unavailable, use an annotated tag and document that choice:

```bash
git tag -a vX.Y.Z -m "codex-ads vX.Y.Z"
```

Before the local tag leaves the machine, scan reachable commits, tree paths,
blobs, commit identities/messages, and annotated tag metadata/message:

```bash
python3 scripts/privacy_doctor.py --history --json
git push origin vX.Y.Z
```

The tag push automatically starts `.github/workflows/release-gate.yml`. Wait
for that exact tag run to pass before creating the GitHub Release. The workflow
also requires `vX.Y.Z`, root `VERSION`, plugin-manifest version, and the exact
`origin/main` commit to agree. If the local tag audit fails, delete only the
unpushed local tag after inspecting the redacted findings; never push it first
and rely on the remote gate to catch it.

Create a GitHub Release from that exact tag. Copy the relevant CHANGELOG entry,
state compatibility and migration behavior, and link to rollback instructions.
Do not call a draft, local tag, failed privacy gate, or unpushed tag a published
release.

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
- Confirm the normal CI and full-history Release Privacy Gate both passed on the
  exact release commit.

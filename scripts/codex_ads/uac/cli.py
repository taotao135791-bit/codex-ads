"""Command-line interface for the deterministic UAC helper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import _validate_case, validate_ledger
from .doctor import doctor_exit_code, render_doctor, run_doctor
from .engine import analyze_case
from .io import _dump, _load
from .ledger import (
    _append_to_ledger_path,
    _cancel_proposal_path,
    _discover_ledger,
    _ledger_context,
    _migrate_ledger_path,
    migrate_ledger,
)
from .normalization import (
    load_normalization_source,
    normalize_uac_input,
    render_normalization,
)
from .quick_ops import decide_case
from .quick_reporting import render_quick_card
from .replay import render_replay, replay_path
from .reporting import render_markdown
from .types import ContractError
from .workspace import (
    Workspace,
    initialize_workspace,
    workspace_migration_notice,
)


def _add_workspace_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        type=Path,
        help="initialized private workspace with safe command-specific default paths",
    )


def _workspace_for(args: argparse.Namespace) -> Workspace | None:
    path = getattr(args, "workspace", None)
    if path is None:
        return None
    return Workspace.at(path)


def _required_path(
    explicit: Path | None,
    workspace_default: Path | None,
    description: str,
) -> Path:
    path = explicit if explicit is not None else workspace_default
    if path is None:
        raise ContractError(f"{description} is required unless --workspace supplies it")
    return path


def _print_migration_notice(path: Path | None, workspace: Workspace | None) -> None:
    if workspace is not None:
        return
    notice = workspace_migration_notice(path)
    if notice:
        print(f"notice: {notice}", file=sys.stderr)


def _display_cli_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def _configure_safe_stdio() -> None:
    """Emit UTF-8 text while escaping only truly unsupported characters."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (OSError, ValueError):
                pass


def _render_json(value: object) -> str:
    """Render standards-compliant ASCII JSON for every stdout machine path."""

    return json.dumps(
        value,
        ensure_ascii=True,
        indent=2,
        default=str,
        allow_nan=False,
    )


def _cli() -> int:
    _configure_safe_stdio()
    parser = argparse.ArgumentParser(
        description="UAC Experiment Loop deterministic helper"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init-workspace", help="initialize a private local UAC workspace"
    )
    init_parser.add_argument("name", help="project name; spaces are supported")
    init_parser.add_argument(
        "--root",
        type=Path,
        default=Path("workspaces"),
        help="parent directory (default: ./workspaces)",
    )

    analyze_parser = subparsers.add_parser("analyze", help="analyze a UAC input file")
    analyze_parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="UAC input file; omit when --workspace can discover it",
    )

    decide_parser = subparsers.add_parser(
        "decide",
        help="return one short, read-only Campaign Level operation card",
        description="Return one short, read-only Campaign Level operation card.",
    )
    decide_parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="UAC input file; omit when --workspace can discover it",
    )
    _add_workspace_argument(decide_parser)
    decide_parser.add_argument("--ledger", type=Path)
    decide_parser.add_argument("--glossary", type=Path)
    decide_parser.add_argument("--question")
    decide_parser.add_argument("--json", action="store_true", dest="json_stdout")
    decide_parser.add_argument("--json-output", type=Path)
    decide_parser.add_argument("--markdown-output", type=Path)
    _add_workspace_argument(analyze_parser)
    analyze_parser.add_argument("--ledger", type=Path)
    analyze_parser.add_argument("--json-output", type=Path)
    analyze_parser.add_argument("--markdown-output", type=Path)
    analyze_parser.add_argument(
        "--append-experiment",
        action="store_true",
        help="after human confirmation, append one unapproved proposal to the selected ledger",
    )

    validate_parser = subparsers.add_parser(
        "validate-ledger", help="validate ADS-EXPERIMENTS"
    )
    validate_parser.add_argument("ledger", nargs="?", type=Path)
    _add_workspace_argument(validate_parser)

    review_parser = subparsers.add_parser(
        "review-ledger", help="review active ledger experiments"
    )
    review_parser.add_argument("ledger", nargs="?", type=Path)
    _add_workspace_argument(review_parser)

    cancel_parser = subparsers.add_parser(
        "cancel-proposal", help="cancel one unexecuted local proposal"
    )
    cancel_parser.add_argument(
        "ledger_or_experiment_id",
        help="legacy ledger path, or experiment ID when --workspace is used",
    )
    cancel_parser.add_argument("experiment_id", nargs="?")
    _add_workspace_argument(cancel_parser)
    cancel_parser.add_argument("--reason", required=True)
    cancel_parser.add_argument(
        "--next-action",
        default="Reassess the account before proposing another experiment.",
    )

    migrate_parser = subparsers.add_parser(
        "migrate-ledger", help="explicitly migrate ADS-EXPERIMENTS"
    )
    migrate_parser.add_argument("ledger", nargs="?", type=Path)
    _add_workspace_argument(migrate_parser)
    migrate_destination = migrate_parser.add_mutually_exclusive_group()
    migrate_destination.add_argument("--output", type=Path)
    migrate_destination.add_argument("--write", action="store_true")

    doctor_parser = subparsers.add_parser(
        "doctor", help="read-only project and environment health check"
    )
    doctor_parser.add_argument("project", nargs="?", type=Path)
    _add_workspace_argument(doctor_parser)
    doctor_parser.add_argument("--input", type=Path)
    doctor_parser.add_argument("--ledger", type=Path)
    doctor_parser.add_argument("--json", action="store_true", dest="json_output")

    normalize_parser = subparsers.add_parser(
        "normalize", help="normalize one UAC summary without making a decision"
    )
    normalize_parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="raw CSV/JSON/YAML summary; omit to discover one in workspace input/",
    )
    _add_workspace_argument(normalize_parser)
    normalize_parser.add_argument(
        "--output",
        type=Path,
        help="explicit normalization envelope path; workspace defaults remain safer",
    )
    normalize_parser.add_argument("--source-label", default="user_provided")

    replay_parser = subparsers.add_parser(
        "replay", help="evaluate one or more anonymized historical replay cases"
    )
    replay_parser.add_argument("path", nargs="?", type=Path)
    _add_workspace_argument(replay_parser)
    replay_parser.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args()
    try:
        if args.command == "init-workspace":
            initialized_workspace = initialize_workspace(args.name, base_dir=args.root)
            displayed_workspace = _display_cli_path(initialized_workspace.root)
            print(f"workspace initialized: {displayed_workspace}")
            print("privacy: workspace contents are git-ignored and must stay local")
            print(
                "minimum data: date range/timezone; country/OS; spend, installs, "
                "registrations, payments; budget/tCPA; conversion delay, measurement "
                "reconciliation, and allowed actions"
            )
            print(
                "next: add one raw CSV/JSON/YAML summary to input/, then run "
                f'normalize --workspace "{displayed_workspace}"'
            )
            return 0

        workspace = _workspace_for(args)
        if args.command == "doctor":
            if workspace is not None and args.project is not None:
                raise ContractError(
                    "doctor accepts either project or --workspace, not both"
                )
            project = (
                workspace.root
                if workspace is not None
                else args.project
                if args.project is not None
                else Path.cwd()
            )
            input_path = args.input
            ledger_path = args.ledger
            if workspace is not None:
                if input_path is not None:
                    input_path = workspace.require_contained_path(
                        input_path, "doctor input"
                    )
                if ledger_path is not None:
                    ledger_path = workspace.require_contained_path(
                        ledger_path, "doctor ledger"
                    )
            if workspace is not None and workspace.initialized:
                if input_path is None:
                    input_path = workspace.discover_case()
                if ledger_path is None:
                    ledger_path = workspace.discover_ledger()
            report = run_doctor(
                project,
                input_path=input_path,
                ledger_path=ledger_path,
                require_workspace=workspace is not None,
            )
            if args.json_output:
                print(_render_json(report))
            else:
                print(render_doctor(report))
            _print_migration_notice(input_path or ledger_path, workspace)
            return doctor_exit_code(report)

        if workspace is not None:
            workspace.require_initialized()

        if args.command == "normalize":
            input_path = _required_path(
                args.input,
                workspace.require_normalization_source()
                if workspace is not None and args.input is None
                else None,
                "normalization input",
            )
            source = load_normalization_source(input_path)
            normalized = normalize_uac_input(source, source_label=args.source_label)
            if args.output:
                output_path = (
                    workspace.require_contained_path(
                        args.output, "normalization output"
                    )
                    if workspace is not None
                    else args.output
                )
                if (
                    output_path.expanduser().resolve()
                    == input_path.expanduser().resolve()
                ):
                    raise ContractError(
                        "normalization output must not overwrite the input"
                    )
                _dump(output_path, normalized)
                print(f"normalized: {output_path}")
            elif workspace is not None:
                for generated_path in (
                    workspace.normalized_input_draft_path,
                    workspace.normalized_input_path,
                    workspace.normalization_report_path,
                ):
                    workspace.require_contained_path(
                        generated_path, "normalization output"
                    )
                if (
                    workspace.normalized_input_draft_path.resolve()
                    == input_path.expanduser().resolve()
                ):
                    raise ContractError(
                        "normalization output must not overwrite the input"
                    )
                contract_error: str | None = None
                try:
                    _validate_case(normalized["normalized"])
                except (ValueError, KeyError, TypeError) as exc:
                    contract_error = str(exc)
                envelope = dict(normalized)
                envelope["analysis_ready"] = contract_error is None
                envelope["contract_error"] = contract_error
                envelope["blocked_ready_input_sha256"] = (
                    workspace.normalized_input_sha256()
                    if contract_error is not None
                    else None
                )
                envelope["next_action"] = (
                    "Run doctor --workspace, then analyze --workspace."
                    if contract_error is None
                    else "Codex must complete the deterministic UAC contract from this "
                    "normalization envelope and save normalized/UAC-INPUT.yaml; do not "
                    "run analysis on the draft."
                )
                _dump(
                    workspace.normalized_input_draft_path,
                    normalized["normalized"],
                )
                if contract_error is None:
                    _dump(workspace.normalized_input_path, normalized["normalized"])
                _dump(workspace.normalization_report_path, envelope)
                print(f"normalized draft: {workspace.normalized_input_draft_path}")
                print(f"normalization report: {workspace.normalization_report_path}")
                if contract_error is None:
                    print(f"analysis-ready input: {workspace.normalized_input_path}")
                    print("next: run doctor --workspace, then analyze --workspace")
                else:
                    print(f"not analysis-ready: {contract_error}")
                    print(
                        "next: Codex must complete normalized/UAC-INPUT.yaml from the "
                        "normalization envelope; do not analyze the draft"
                    )
            else:
                print(render_normalization(normalized))
            if workspace is not None:
                for generated_path in (
                    args.output,
                    workspace.normalized_input_draft_path,
                    workspace.normalized_input_path,
                    workspace.normalization_report_path,
                ):
                    if generated_path is not None and generated_path.is_file():
                        workspace.protect_file(generated_path)
            _print_migration_notice(input_path, workspace)
            return 0

        if args.command == "decide":
            input_path = _required_path(
                args.input,
                workspace.require_case()
                if workspace is not None and args.input is None
                else None,
                "UAC input",
            )
            if workspace is not None:
                input_path = workspace.require_contained_path(input_path, "UAC input")
            ledger_path = args.ledger
            if ledger_path is None:
                ledger_path = (
                    workspace.ledger_path
                    if workspace is not None
                    else _discover_ledger(input_path)
                )
            if workspace is not None and ledger_path is not None:
                ledger_path = workspace.require_contained_path(
                    ledger_path, "ledger path"
                )

            project_glossary: object = {}
            glossary_path: Path | None = None
            if workspace is not None:
                context = _load(workspace.context_path)
                if isinstance(context, dict):
                    project_glossary = context.get("campaign_level_glossary", {})
            if args.glossary is not None:
                glossary_path = args.glossary
                if workspace is not None:
                    glossary_path = workspace.require_contained_path(
                        glossary_path, "campaign level glossary"
                    )
                glossary_document = _load(glossary_path)
                if isinstance(glossary_document, dict):
                    project_glossary = glossary_document.get(
                        "campaign_level_glossary", glossary_document
                    )
                else:
                    raise ContractError("campaign level glossary must be an object")
            if not isinstance(project_glossary, dict):
                raise ContractError("campaign level glossary must be an object")

            json_output = args.json_output
            markdown_output = args.markdown_output
            if workspace is not None:
                if json_output is None:
                    json_output = workspace.quick_decision_path
                if markdown_output is None:
                    markdown_output = workspace.quick_decision_report_path
                json_output = workspace.require_contained_path(
                    json_output, "Quick Decision JSON output"
                )
                markdown_output = workspace.require_contained_path(
                    markdown_output, "Quick Decision Markdown output"
                )

            protected_paths = {input_path.expanduser().resolve()}
            if ledger_path is not None:
                protected_paths.add(ledger_path.expanduser().resolve())
            if glossary_path is not None:
                protected_paths.add(glossary_path.expanduser().resolve())
            if workspace is not None:
                protected_paths.update(
                    {
                        workspace.context_path.expanduser().resolve(),
                        workspace.gitignore_path.expanduser().resolve(),
                    }
                )
            output_paths = [
                path.expanduser().resolve()
                for path in (json_output, markdown_output)
                if path is not None
            ]
            if len(output_paths) != len(set(output_paths)):
                raise ContractError(
                    "Quick Decision JSON and Markdown output paths must be different"
                )
            if any(path in protected_paths for path in output_paths):
                raise ContractError(
                    "Quick Decision outputs must not overwrite input, ledger, glossary, or Workspace control files"
                )

            case = _load(input_path)
            ledger = (
                _load(ledger_path) if ledger_path and ledger_path.exists() else None
            )
            result = decide_case(
                case,
                ledger,
                question=args.question,
                project_glossary=project_glossary,
            )
            card = render_quick_card(result)
            if json_output is not None:
                _dump(json_output, result)
            if markdown_output is not None:
                markdown_output.parent.mkdir(parents=True, exist_ok=True)
                markdown_output.write_text(card, encoding="utf-8")
            if workspace is not None:
                for generated_path in (json_output, markdown_output):
                    if generated_path is not None and generated_path.is_file():
                        workspace.protect_file(generated_path)
            if args.json_stdout:
                print(_render_json(result))
            else:
                print(card, end="")
                if workspace is not None:
                    print(f"structured decision: {json_output}")
                    print(f"operation card: {markdown_output}")
                    print("ledger: unchanged (Quick Decision is not an experiment)")
            _print_migration_notice(input_path, workspace)
            return 0

        if args.command == "replay":
            replay_target = _required_path(
                args.path,
                workspace.replays_dir if workspace is not None else None,
                "replay path",
            )
            if workspace is not None:
                replay_target = workspace.require_contained_path(
                    replay_target, "replay path"
                )
            report = replay_path(replay_target)
            if args.json_output:
                print(_render_json(report))
            else:
                print(render_replay(report))
            return 0

        if args.command == "validate-ledger":
            ledger_path = _required_path(
                args.ledger,
                workspace.ledger_path if workspace is not None else None,
                "ledger path",
            )
            if workspace is not None:
                ledger_path = workspace.require_contained_path(
                    ledger_path, "ledger path"
                )
            errors = validate_ledger(_load(ledger_path))
            if errors:
                raise ContractError("; ".join(errors))
            print(f"valid: {ledger_path}")
            _print_migration_notice(ledger_path, workspace)
            return 0

        if args.command == "review-ledger":
            ledger_path = _required_path(
                args.ledger,
                workspace.ledger_path if workspace is not None else None,
                "ledger path",
            )
            if workspace is not None:
                ledger_path = workspace.require_contained_path(
                    ledger_path, "ledger path"
                )
            reviews, learnings = _ledger_context(_load(ledger_path))
            print(_render_json({"reviews": reviews, "learnings": learnings}))
            _print_migration_notice(ledger_path, workspace)
            return 0

        if args.command == "cancel-proposal":
            if args.experiment_id is None:
                if workspace is None:
                    raise ContractError(
                        "cancel-proposal requires LEDGER EXPERIMENT_ID, or "
                        "EXPERIMENT_ID with --workspace"
                    )
                ledger_path = workspace.ledger_path
                experiment_id = args.ledger_or_experiment_id
            else:
                if workspace is not None:
                    raise ContractError(
                        "with --workspace, pass only EXPERIMENT_ID; an external ledger "
                        "path is not allowed"
                    )
                ledger_path = Path(args.ledger_or_experiment_id)
                experiment_id = args.experiment_id
            if workspace is not None:
                ledger_path = workspace.require_contained_path(
                    ledger_path, "ledger path"
                )
            _cancel_proposal_path(
                ledger_path, experiment_id, args.reason, args.next_action
            )
            print(f"cancelled: {experiment_id}")
            _print_migration_notice(ledger_path, workspace)
            return 0

        if args.command == "migrate-ledger":
            ledger_path = _required_path(
                args.ledger,
                workspace.ledger_path if workspace is not None else None,
                "ledger path",
            )
            if workspace is not None:
                ledger_path = workspace.require_contained_path(
                    ledger_path, "ledger path"
                )
            if args.write:
                _migrate_ledger_path(ledger_path)
                print(f"migrated: {ledger_path}")
                _print_migration_notice(ledger_path, workspace)
                return 0
            migrated = migrate_ledger(_load(ledger_path))
            if args.output:
                output_path = (
                    workspace.require_contained_path(args.output, "migration output")
                    if workspace is not None
                    else args.output
                )
                source_path = ledger_path.expanduser().resolve()
                resolved_output_path = output_path.expanduser().resolve()
                if resolved_output_path == source_path:
                    raise ContractError(
                        "migration output must not overwrite the source; use --write"
                    )
                _dump(output_path, migrated)
                print(f"migrated: {output_path}")
            else:
                print(_render_json(migrated))
            _print_migration_notice(ledger_path, workspace)
            return 0

        input_path = _required_path(
            args.input,
            workspace.require_case()
            if workspace is not None and args.input is None
            else None,
            "UAC input",
        )
        if workspace is not None:
            input_path = workspace.require_contained_path(input_path, "UAC input")
        ledger_path = args.ledger
        if ledger_path is None:
            ledger_path = (
                workspace.ledger_path
                if workspace is not None
                else _discover_ledger(input_path)
            )
        if workspace is not None and ledger_path is not None:
            ledger_path = workspace.require_contained_path(ledger_path, "ledger path")

        json_output = args.json_output
        markdown_output = args.markdown_output
        if workspace is not None:
            if json_output is None:
                json_output = workspace.analysis_path
            if markdown_output is None:
                markdown_output = workspace.report_path
            if json_output is not None:
                json_output = workspace.require_contained_path(
                    json_output, "JSON output"
                )
            if markdown_output is not None:
                markdown_output = workspace.require_contained_path(
                    markdown_output, "Markdown output"
                )

        protected_paths = {input_path.expanduser().resolve()}
        if ledger_path:
            protected_paths.add(ledger_path.expanduser().resolve())
        output_paths = [
            path.expanduser().resolve()
            for path in (json_output, markdown_output)
            if path is not None
        ]
        if len(output_paths) != len(set(output_paths)):
            raise ContractError("JSON and Markdown output paths must be different")
        if any(path in protected_paths for path in output_paths):
            raise ContractError("output paths must not overwrite the input or ledger")

        case = _load(input_path)
        ledger = _load(ledger_path) if ledger_path and ledger_path.exists() else None
        result = analyze_case(case, ledger)
        if json_output:
            _dump(json_output, result)
        if markdown_output:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(render_markdown(result), encoding="utf-8")
        if workspace is not None:
            for generated_path in (json_output, markdown_output):
                if generated_path is not None and generated_path.is_file():
                    workspace.protect_file(generated_path)
        if args.append_experiment:
            if not ledger_path:
                raise ContractError("--append-experiment requires --ledger")
            _append_to_ledger_path(ledger_path, result)
            if workspace is not None:
                workspace.protect_file(ledger_path)
        if not json_output and not markdown_output:
            print(_render_json(result))
        elif workspace is not None:
            print(f"analysis: {json_output}")
            print(f"report: {markdown_output}")
            print(
                "ledger: proposal appended"
                if args.append_experiment
                else "ledger: unchanged (human confirmation is required before append)"
            )
        _print_migration_notice(input_path, workspace)
        return 0
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


main = _cli

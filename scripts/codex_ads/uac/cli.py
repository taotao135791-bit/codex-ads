"""Command-line interface for the deterministic UAC helper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import validate_ledger
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
from .replay import render_replay, replay_path
from .reporting import render_markdown
from .types import ContractError


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="UAC Experiment Loop deterministic helper"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="analyze a UAC input file")
    analyze_parser.add_argument("input", type=Path)
    analyze_parser.add_argument("--ledger", type=Path)
    analyze_parser.add_argument("--json-output", type=Path)
    analyze_parser.add_argument("--markdown-output", type=Path)
    analyze_parser.add_argument(
        "--append-experiment",
        action="store_true",
        help="append only an unapproved proposed experiment to --ledger",
    )

    validate_parser = subparsers.add_parser(
        "validate-ledger", help="validate ADS-EXPERIMENTS"
    )
    validate_parser.add_argument("ledger", type=Path)

    review_parser = subparsers.add_parser(
        "review-ledger", help="review active ledger experiments"
    )
    review_parser.add_argument("ledger", type=Path)

    cancel_parser = subparsers.add_parser(
        "cancel-proposal", help="cancel one unexecuted local proposal"
    )
    cancel_parser.add_argument("ledger", type=Path)
    cancel_parser.add_argument("experiment_id")
    cancel_parser.add_argument("--reason", required=True)
    cancel_parser.add_argument(
        "--next-action",
        default="Reassess the account before proposing another experiment.",
    )

    migrate_parser = subparsers.add_parser(
        "migrate-ledger", help="explicitly migrate ADS-EXPERIMENTS"
    )
    migrate_parser.add_argument("ledger", type=Path)
    migrate_destination = migrate_parser.add_mutually_exclusive_group()
    migrate_destination.add_argument("--output", type=Path)
    migrate_destination.add_argument("--write", action="store_true")

    doctor_parser = subparsers.add_parser(
        "doctor", help="read-only project and environment health check"
    )
    doctor_parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    doctor_parser.add_argument("--input", type=Path)
    doctor_parser.add_argument("--ledger", type=Path)
    doctor_parser.add_argument("--json", action="store_true", dest="json_output")

    normalize_parser = subparsers.add_parser(
        "normalize", help="normalize one UAC summary without making a decision"
    )
    normalize_parser.add_argument("input", type=Path)
    normalize_parser.add_argument("--output", type=Path)
    normalize_parser.add_argument("--source-label", default="user_provided")

    replay_parser = subparsers.add_parser(
        "replay", help="evaluate one or more anonymized historical replay cases"
    )
    replay_parser.add_argument("path", type=Path)
    replay_parser.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args()
    try:
        if args.command == "doctor":
            report = run_doctor(
                args.project, input_path=args.input, ledger_path=args.ledger
            )
            if args.json_output:
                print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            else:
                print(render_doctor(report))
            return doctor_exit_code(report)
        if args.command == "normalize":
            source = load_normalization_source(args.input)
            normalized = normalize_uac_input(source, source_label=args.source_label)
            if args.output:
                if (
                    args.output.expanduser().resolve()
                    == args.input.expanduser().resolve()
                ):
                    raise ContractError(
                        "normalization output must not overwrite the input"
                    )
                _dump(args.output, normalized)
                print(f"normalized: {args.output}")
            else:
                print(render_normalization(normalized))
            return 0
        if args.command == "replay":
            report = replay_path(args.path)
            if args.json_output:
                print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            else:
                print(render_replay(report))
            return 0
        if args.command == "validate-ledger":
            errors = validate_ledger(_load(args.ledger))
            if errors:
                raise ContractError("; ".join(errors))
            print(f"valid: {args.ledger}")
            return 0
        if args.command == "review-ledger":
            reviews, learnings = _ledger_context(_load(args.ledger))
            print(
                json.dumps(
                    {"reviews": reviews, "learnings": learnings},
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return 0
        if args.command == "cancel-proposal":
            _cancel_proposal_path(
                args.ledger, args.experiment_id, args.reason, args.next_action
            )
            print(f"cancelled: {args.experiment_id}")
            return 0
        if args.command == "migrate-ledger":
            if args.write:
                _migrate_ledger_path(args.ledger)
                print(f"migrated: {args.ledger}")
                return 0
            migrated = migrate_ledger(_load(args.ledger))
            if args.output:
                source_path = args.ledger.expanduser().resolve()
                output_path = args.output.expanduser().resolve()
                if output_path == source_path:
                    raise ContractError(
                        "migration output must not overwrite the source; use --write"
                    )
                _dump(args.output, migrated)
                print(f"migrated: {args.output}")
            else:
                print(
                    json.dumps(
                        migrated,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )
                )
            return 0

        if args.ledger is None:
            args.ledger = _discover_ledger(args.input)

        protected_paths = {args.input.expanduser().resolve()}
        if args.ledger:
            protected_paths.add(args.ledger.expanduser().resolve())
        output_paths = [
            path.expanduser().resolve()
            for path in (args.json_output, args.markdown_output)
            if path is not None
        ]
        if len(output_paths) != len(set(output_paths)):
            raise ContractError("JSON and Markdown output paths must be different")
        if any(path in protected_paths for path in output_paths):
            raise ContractError("output paths must not overwrite the input or ledger")

        case = _load(args.input)
        ledger = _load(args.ledger) if args.ledger and args.ledger.exists() else None
        result = analyze_case(case, ledger)
        if args.json_output:
            _dump(args.json_output, result)
        if args.markdown_output:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(render_markdown(result), encoding="utf-8")
        if args.append_experiment:
            if not args.ledger:
                raise ContractError("--append-experiment requires --ledger")
            _append_to_ledger_path(args.ledger, result)
        if not args.json_output and not args.markdown_output:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
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

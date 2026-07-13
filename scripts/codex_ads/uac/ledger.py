"""Experiment-ledger context, discovery, and local mutation helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from .contracts import validate_ledger
from .io import _dump, _load
from .review import review_experiment
from .types import CURRENT_LEDGER_SCHEMA_VERSION, ContractError


@contextmanager
def _ledger_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ContractError(f"ledger is locked by another process: {path}") from exc
    try:
        os.close(descriptor)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _ledger_context(
    ledger: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not ledger:
        return [], []
    errors = validate_ledger(ledger)
    if errors:
        raise ContractError("invalid experiment ledger: " + "; ".join(errors))
    reviews: list[dict[str, Any]] = []
    learnings: list[dict[str, Any]] = []
    for item in ledger["experiments"]:
        status = item["status"]
        if status == "proposed":
            review = {
                "id": item["id"],
                "status": "PROPOSED_NOT_EXECUTED",
                "reasons": ["proposal is not approved or executed"],
                "active": False,
            }
        elif status == "approved" and not item.get("execution", {}).get("executed_at"):
            review = {
                "id": item["id"],
                "status": "APPROVED_NOT_EXECUTED",
                "reasons": ["experiment is approved but execution is not recorded"],
                "active": False,
            }
        elif status == "cancelled":
            review = {
                "id": item["id"],
                "status": "CANCELLED_NOT_EXECUTED",
                "reasons": ["proposal was explicitly cancelled before execution"],
                "active": False,
            }
        else:
            review = review_experiment(item)
            review["active"] = status in {"running", "observing"}
        reviews.append(review)

        learning = item.get("decision", {}).get("learning")
        terminal_learning = status in {"completed", "stopped"} and review["status"] in {
            "WIN",
            "LOSS",
            "INCONCLUSIVE",
            "INVALIDATED",
            "STOPPED_FOR_GUARDRAIL",
            "CONFOUNDED",
        }
        if terminal_learning and isinstance(learning, dict):
            learnings.append(
                {
                    "experiment_id": item["id"],
                    "scope": learning["scope"],
                    "statement": learning["statement"],
                    "evidence": deepcopy(learning.get("evidence", [])),
                }
            )
    return reviews, learnings


def _append_proposal(ledger: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    proposals = result.get("experiments", [])
    if not proposals:
        raise ContractError("analysis did not produce an experiment proposal")
    updated = deepcopy(ledger)
    updated.setdefault("schema_version", CURRENT_LEDGER_SCHEMA_VERSION)
    updated.setdefault("project", {"name": "anonymized-uac-project"})
    updated.setdefault("experiments", [])
    if any(item.get("id") == proposals[0]["id"] for item in updated["experiments"]):
        raise ContractError(f"experiment id already exists: {proposals[0]['id']}")
    updated["experiments"].append(proposals[0])
    errors = validate_ledger(updated)
    if errors:
        raise ContractError("updated ledger is invalid: " + "; ".join(errors))
    return updated


def _append_to_ledger_path(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _ledger_lock(path):
        current = (
            _load(path)
            if path.exists()
            else {
                "schema_version": CURRENT_LEDGER_SCHEMA_VERSION,
                "experiments": [],
            }
        )
        _dump(path, _append_proposal(current, result))


def _cancel_proposal_path(
    path: Path, experiment_id: str, reason: str, next_action: str
) -> None:
    if not reason.strip():
        raise ContractError("cancellation reason must be non-empty")
    if not next_action.strip():
        raise ContractError("cancellation next action must be non-empty")
    with _ledger_lock(path):
        ledger = _load(path)
        errors = validate_ledger(ledger)
        if errors:
            raise ContractError("invalid experiment ledger: " + "; ".join(errors))
        matches = [
            item for item in ledger["experiments"] if item.get("id") == experiment_id
        ]
        if not matches:
            raise ContractError(f"experiment id not found: {experiment_id}")
        experiment = matches[0]
        if experiment.get("status") != "proposed":
            raise ContractError(
                "only an unexecuted proposed experiment can be cancelled"
            )
        experiment["status"] = "cancelled"
        experiment["execution"] = {
            "approved": False,
            "executed_at": None,
            "notes": reason,
        }
        experiment["result"].update(
            {
                "status": "INVALIDATED",
                "metrics": {},
                "confounders": [],
                "evidence_quality": "not_executed",
            }
        )
        experiment["result"].pop("evaluation", None)
        experiment["result"].pop("rule_evaluation", None)
        experiment["result"].pop("review_snapshot", None)
        experiment["decision"] = {
            "outcome": "CANCELLED",
            "next_action": next_action,
            "learning": None,
        }
        errors = validate_ledger(ledger)
        if errors:
            raise ContractError("cancelled ledger is invalid: " + "; ".join(errors))
        _dump(path, ledger)


def _discover_ledger(input_path: Path) -> Path | None:
    roots = (input_path.expanduser().resolve().parent, Path.cwd().resolve())
    candidates = {
        (root / name).resolve()
        for root in roots
        for name in (
            "ADS-EXPERIMENTS.yaml",
            "ADS-EXPERIMENTS.yml",
            "ADS-EXPERIMENTS.json",
        )
        if (root / name).is_file()
    }
    if len(candidates) > 1:
        paths = ", ".join(str(path) for path in sorted(candidates))
        raise ContractError(
            "multiple experiment ledgers were discovered; select one with --ledger: "
            + paths
        )
    return next(iter(candidates), None)


def migrate_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Return an explicit, lossless ledger migration to the current schema."""
    errors = validate_ledger(ledger)
    if errors:
        raise ContractError("invalid experiment ledger: " + "; ".join(errors))
    migrated = deepcopy(ledger)
    migrated["schema_version"] = CURRENT_LEDGER_SCHEMA_VERSION
    return migrated


def _migrate_ledger_path(path: Path) -> None:
    """Lock, re-read, validate, and atomically migrate one ledger in place."""

    with _ledger_lock(path):
        _dump(path, migrate_ledger(_load(path)))

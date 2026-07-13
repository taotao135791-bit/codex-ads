"""Read-only health checks for a local UAC project and runtime environment."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from .contracts import _validate_case, validate_ledger
from .io import _load
from .review import review_experiment
from .types import (
    CURRENT_LEDGER_SCHEMA_VERSION,
    SUPPORTED_LEDGER_SCHEMA_VERSIONS,
)
from .version import read_project_version


_INPUT_NAMES = ("UAC-INPUT.yaml", "UAC-INPUT.yml", "UAC-INPUT.json")
_LEDGER_NAMES = (
    "ADS-EXPERIMENTS.yaml",
    "ADS-EXPERIMENTS.yml",
    "ADS-EXPERIMENTS.json",
)
_REQUIRED_ASSETS = (
    "UAC-INPUT.example.yaml",
    "ADS-EXPERIMENTS.minimal.yaml",
    "ads-experiments.schema.json",
    "ads-experiments-v1.0.schema.json",
    "uac-analysis.schema.json",
)


def _check(
    check_id: str, status: str, message: str, *, detail: Any = None
) -> dict[str, Any]:
    return {"id": check_id, "status": status, "message": message, "detail": detail}


def _display_path(path: Path | None, project: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return path.name


def _safe_error(exc: Exception, path: Path | None = None) -> str:
    message = str(exc)
    if path is not None:
        message = message.replace(str(path), path.name)
        try:
            message = message.replace(str(path.resolve()), path.name)
        except OSError:
            pass
    return message


def _runtime_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _find_assets(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit.expanduser().resolve()
    root = _runtime_root()
    candidates = (
        root / "skills" / "ads-google-app" / "assets",
        root.parent / "ads-google-app" / "assets",
        root / "assets",
    )
    return next((candidate for candidate in candidates if candidate.is_dir()), None)


def _discover_one(
    project: Path, names: tuple[str, ...], explicit: Path | None
) -> tuple[Path | None, list[Path]]:
    if explicit is not None:
        path = explicit.expanduser()
        if not path.is_absolute():
            path = project / path
        return path.resolve(), [path.resolve()] if path.is_file() else []
    matches = [
        (project / name).resolve() for name in names if (project / name).is_file()
    ]
    return (matches[0] if len(matches) == 1 else None), matches


def _status_summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        status.lower(): sum(check["status"] == status for check in checks)
        for status in ("PASS", "WARN", "FAIL")
    }


def run_doctor(
    project: Path,
    *,
    input_path: Path | None = None,
    ledger_path: Path | None = None,
    assets_dir: Path | None = None,
) -> dict[str, Any]:
    """Inspect project state without creating or changing any file."""

    project = project.expanduser().resolve()
    checks: list[dict[str, Any]] = []
    version = read_project_version()

    python_supported = sys.version_info >= (3, 10)
    checks.append(
        _check(
            "python-version",
            "PASS" if python_supported else "FAIL",
            f"Python {sys.version_info.major}.{sys.version_info.minor} detected; 3.10+ required",
        )
    )
    checks.append(
        _check(
            "project-version",
            "PASS" if version not in {"unknown", "invalid"} else "FAIL",
            f"codex-ads version: {version}",
        )
    )

    yaml_available = importlib.util.find_spec("yaml") is not None
    jsonschema_available = importlib.util.find_spec("jsonschema") is not None
    checks.append(
        _check(
            "required-dependency:pyyaml",
            "PASS" if yaml_available else "FAIL",
            "PyYAML is available"
            if yaml_available
            else "PyYAML is required for YAML workflows",
        )
    )
    checks.append(
        _check(
            "optional-dependency:jsonschema",
            "PASS" if jsonschema_available else "WARN",
            "jsonschema is available"
            if jsonschema_available
            else "jsonschema is optional; runtime validation remains available",
        )
    )
    checks.append(
        _check(
            "api-credentials",
            "PASS",
            "Deterministic UAC analysis requires no advertising or model API key",
        )
    )

    if not project.is_dir():
        checks.append(
            _check("project-directory", "FAIL", "project directory is missing")
        )
    else:
        checks.append(_check("project-directory", "PASS", "project directory exists"))
        writable = os.access(project, os.W_OK)
        checks.append(
            _check(
                "output-write-permission",
                "PASS" if writable else "FAIL",
                "project output directory is writable"
                if writable
                else "project output directory is not writable",
            )
        )

    assets = _find_assets(assets_dir)
    missing_assets: list[str] = []
    if assets is None:
        missing_assets = list(_REQUIRED_ASSETS)
    else:
        missing_assets = [
            name for name in _REQUIRED_ASSETS if not (assets / name).is_file()
        ]
    checks.append(
        _check(
            "uac-assets",
            "PASS" if not missing_assets else "FAIL",
            "required UAC schemas and examples are available"
            if not missing_assets
            else "required UAC assets are missing",
            detail=missing_assets,
        )
    )

    schema_valid = False
    if assets is not None and not missing_assets:
        try:
            current_schema = json.loads(
                (assets / "ads-experiments.schema.json").read_text(encoding="utf-8")
            )
            legacy_schema = json.loads(
                (assets / "ads-experiments-v1.0.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            schema_valid = bool(
                current_schema.get("$schema") and legacy_schema.get("$schema")
            )
            if jsonschema_available:
                import jsonschema

                jsonschema.Draft202012Validator.check_schema(current_schema)
                jsonschema.Draft202012Validator.check_schema(legacy_schema)
        # Doctor is an error boundary: malformed third-party schema objects must
        # become a clean FAIL check rather than a traceback.
        except Exception as exc:
            checks.append(
                _check(
                    "schema-json", "FAIL", f"schema JSON is invalid: {_safe_error(exc)}"
                )
            )
        else:
            checks.append(
                _check(
                    "schema-json",
                    "PASS" if schema_valid else "FAIL",
                    "current and legacy ledger schemas parse correctly"
                    if schema_valid
                    else "schema documents are missing a declared JSON Schema dialect",
                )
            )

    selected_input, input_matches = _discover_one(project, _INPUT_NAMES, input_path)
    input_valid = False
    if input_path is not None and not input_matches:
        checks.append(_check("uac-input", "FAIL", "explicit UAC input file is missing"))
    elif len(input_matches) > 1:
        checks.append(
            _check(
                "uac-input",
                "WARN",
                "multiple UAC input files found; select one explicitly",
                detail=[_display_path(path, project) for path in input_matches],
            )
        )
    elif selected_input is None:
        checks.append(
            _check(
                "uac-input",
                "WARN",
                "no UAC-INPUT file found; add one or pass --input",
            )
        )
    else:
        try:
            _validate_case(_load(selected_input))
            input_valid = True
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks.append(
                _check(
                    "uac-input",
                    "FAIL",
                    f"UAC input is invalid: {_safe_error(exc, selected_input)}",
                )
            )
        else:
            checks.append(_check("uac-input", "PASS", "UAC input contract is valid"))

    selected_ledger, ledger_matches = _discover_one(project, _LEDGER_NAMES, ledger_path)
    ledger_valid = False
    needs_migration = False
    open_statuses: list[str] = []
    waiting_ids: list[str] = []
    confounded_ids: list[str] = []
    ready_review_ids: list[str] = []
    ledger_version: str | None = None
    if ledger_path is not None and not ledger_matches:
        checks.append(
            _check("experiment-ledger", "FAIL", "explicit experiment ledger is missing")
        )
    elif len(ledger_matches) > 1:
        checks.append(
            _check(
                "experiment-ledger",
                "FAIL",
                "multiple experiment ledgers found; select one explicitly",
                detail=[_display_path(path, project) for path in ledger_matches],
            )
        )
    elif selected_ledger is None:
        checks.append(
            _check(
                "experiment-ledger",
                "WARN",
                "no experiment ledger found; copy the minimal template before recording a proposal",
            )
        )
    else:
        try:
            ledger = _load(selected_ledger)
            errors = validate_ledger(ledger)
            if errors:
                raise ValueError("; ".join(errors))
            ledger_valid = True
            ledger_version = str(ledger.get("schema_version"))
            needs_migration = ledger_version != CURRENT_LEDGER_SCHEMA_VERSION
            for experiment in ledger["experiments"]:
                status = experiment["status"]
                if status in {"proposed", "approved", "running", "observing"}:
                    open_statuses.append(status)
                if status in {"running", "observing"}:
                    review = review_experiment(experiment)
                    if review["status"] in {
                        "WAITING_FOR_MATURITY",
                        "INSUFFICIENT_VOLUME",
                    }:
                        waiting_ids.append(str(experiment["id"]))
                    if review["status"] == "CONFOUNDED":
                        confounded_ids.append(str(experiment["id"]))
                    if review["status"] in {
                        "WIN",
                        "LOSS",
                        "INCONCLUSIVE",
                        "STOPPED_FOR_GUARDRAIL",
                        "INVALIDATED",
                    }:
                        ready_review_ids.append(str(experiment["id"]))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            checks.append(
                _check(
                    "experiment-ledger",
                    "FAIL",
                    f"experiment ledger is invalid: {_safe_error(exc, selected_ledger)}",
                )
            )
        else:
            checks.append(
                _check(
                    "experiment-ledger", "PASS", "experiment ledger contract is valid"
                )
            )
            checks.append(
                _check(
                    "ledger-schema-version",
                    "WARN" if needs_migration else "PASS",
                    f"ledger schema {ledger_version} is supported but migration to {CURRENT_LEDGER_SCHEMA_VERSION} is available"
                    if needs_migration
                    else f"ledger schema is current ({CURRENT_LEDGER_SCHEMA_VERSION})",
                    detail={
                        "supported": sorted(SUPPORTED_LEDGER_SCHEMA_VERSIONS),
                        "current": CURRENT_LEDGER_SCHEMA_VERSION,
                    },
                )
            )
            checks.append(
                _check(
                    "open-experiments",
                    "WARN" if open_statuses else "PASS",
                    "unfinished experiments require review before a new proposal"
                    if open_statuses
                    else "no unfinished experiment blocks a new proposal",
                    detail={"statuses": open_statuses},
                )
            )
            checks.append(
                _check(
                    "ready-for-review",
                    "WARN" if ready_review_ids else "PASS",
                    "an active experiment has enough evidence for terminal review"
                    if ready_review_ids
                    else "no active experiment is waiting for terminal result entry",
                    detail={"count": len(ready_review_ids)},
                )
            )
            checks.append(
                _check(
                    "waiting-maturity",
                    "WARN" if waiting_ids else "PASS",
                    "an experiment is waiting for maturity or conversion volume"
                    if waiting_ids
                    else "no active experiment is waiting for maturity",
                    detail={"count": len(waiting_ids)},
                )
            )
            checks.append(
                _check(
                    "confounded-experiments",
                    "WARN" if confounded_ids else "PASS",
                    "an active experiment is confounded and cannot support attribution"
                    if confounded_ids
                    else "no active experiment is marked confounded",
                    detail={"count": len(confounded_ids)},
                )
            )

    if any(check["status"] == "FAIL" for check in checks):
        next_action = "修复 FAIL 项后再运行分析或创建实验。"
    elif needs_migration:
        next_action = "先预览 migrate-ledger；确认后显式写入或输出 1.1 台账。"
    elif confounded_ids:
        next_action = "停止归因判断，记录混杂因素并由人工决定重启或结束实验。"
    elif ready_review_ids:
        next_action = "当前实验已达到复盘条件；回填终态结果和下一步，不要先创建新实验。"
    elif waiting_ids:
        next_action = "当前不应创建新实验；等待观察期、转化量和回传延迟成熟。"
    elif open_statuses:
        next_action = "先处理未完成实验；审批、执行、取消或到期复盘后再提新变量。"
    elif not input_valid:
        next_action = "补充或修复 UAC 输入；缺失字段会导致错误行动时必须停止。"
    elif not ledger_valid:
        next_action = "复制最小台账模板；当前可只读分析，但不能记录实验闭环。"
    else:
        next_action = "当前可以运行确定性分析；仍需人工确认任何实验提案。"

    summary = _status_summary(checks)
    status = "FAIL" if summary["fail"] else "WARN" if summary["warn"] else "PASS"
    return {
        "schema_version": "1.0",
        "status": status,
        "version": version,
        "project": ".",
        "files": {
            "input": _display_path(selected_input, project),
            "ledger": _display_path(selected_ledger, project),
            "assets_available": assets is not None,
        },
        "summary": summary,
        "checks": checks,
        "next_action": next_action,
        "mutated_files": False,
    }


def doctor_exit_code(report: dict[str, Any]) -> int:
    return 2 if report["status"] == "FAIL" else 0


def render_doctor(report: dict[str, Any]) -> str:
    lines = [
        f"UAC Doctor: {report['status']} (codex-ads {report['version']})",
        f"PASS {report['summary']['pass']} / WARN {report['summary']['warn']} / FAIL {report['summary']['fail']}",
    ]
    lines.extend(
        f"[{check['status']}] {check['id']}: {check['message']}"
        for check in report["checks"]
    )
    lines.extend(("", f"下一步：{report['next_action']}", "Doctor 未修改任何文件。"))
    return "\n".join(lines)

#!/usr/bin/env python3
"""Compatibility entry point for the deterministic UAC experiment helper.

The implementation lives under codex_ads.uac. Existing imports and CLI
invocations continue to use this module.
"""

from __future__ import annotations

from codex_ads.uac import (
    ANALYSIS_SCHEMA_VERSION,
    CURRENT_LEDGER_SCHEMA_VERSION,
    EvidenceQuality,
    EVIDENCE_QUALITY_STATES,
    ExperimentOutcome,
    ExperimentStatus,
    EXPERIMENT_RESULTS,
    EXPERIMENT_STATUSES,
    FeasibilityState,
    FEASIBILITY_STATES,
    LearningScope,
    LearningState,
    LEARNING_SCOPES,
    LEARNING_STATES,
    MeasurementState,
    MEASUREMENT_STATES,
    PermissionClass,
    PERMISSION_CLASSES,
    SUPPORTED_LEDGER_SCHEMA_VERSIONS,
    TERMINAL_EXPERIMENT_RESULTS,
    ContractError,
    Workspace,
    analyze_case,
    decide_case,
    derive_signals,
    initialize_workspace,
    migrate_ledger,
    normalize_uac_input,
    recommend_numeric,
    replay_path,
    render_quick_card,
    render_markdown,
    review_experiment,
    run_doctor,
    route_question,
    validate_analysis,
    validate_experiment,
    validate_ledger,
    validate_workspace_name,
)
from codex_ads.uac.cli import _cli, main

__all__ = [
    "ContractError",
    "Workspace",
    "MeasurementState",
    "LearningState",
    "FeasibilityState",
    "PermissionClass",
    "ExperimentStatus",
    "ExperimentOutcome",
    "EvidenceQuality",
    "LearningScope",
    "ANALYSIS_SCHEMA_VERSION",
    "CURRENT_LEDGER_SCHEMA_VERSION",
    "SUPPORTED_LEDGER_SCHEMA_VERSIONS",
    "MEASUREMENT_STATES",
    "LEARNING_STATES",
    "FEASIBILITY_STATES",
    "PERMISSION_CLASSES",
    "EXPERIMENT_RESULTS",
    "TERMINAL_EXPERIMENT_RESULTS",
    "EXPERIMENT_STATUSES",
    "EVIDENCE_QUALITY_STATES",
    "LEARNING_SCOPES",
    "analyze_case",
    "decide_case",
    "derive_signals",
    "initialize_workspace",
    "review_experiment",
    "validate_experiment",
    "validate_ledger",
    "validate_analysis",
    "render_markdown",
    "render_quick_card",
    "migrate_ledger",
    "run_doctor",
    "route_question",
    "normalize_uac_input",
    "recommend_numeric",
    "replay_path",
    "validate_workspace_name",
    "_cli",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared UAC wire-state constants and contract errors."""

from __future__ import annotations

from .models import (
    BudgetDeliveryState,
    CalculationEvidenceType,
    EvidenceQuality,
    EventVolumeState,
    ExperimentOutcome,
    ExperimentStatus,
    FeasibilityState,
    LearningScope,
    LearningState,
    MaturityState,
    MeasurementState,
    PermissionClass,
    SplitFeasibilityState,
    TargetConstraintState,
    ValueSignalState,
)


ANALYSIS_SCHEMA_VERSION = "1.0"
CURRENT_LEDGER_SCHEMA_VERSION = "1.1"
SUPPORTED_LEDGER_SCHEMA_VERSIONS = frozenset({"1.0", "1.1"})


MEASUREMENT_STATES = {state.value for state in MeasurementState}


LEARNING_STATES = {state.value for state in LearningState}


FEASIBILITY_STATES = {state.value for state in FeasibilityState}


PERMISSION_CLASSES = {state.value for state in PermissionClass}


EXPERIMENT_RESULTS = {state.value for state in ExperimentOutcome}


TERMINAL_EXPERIMENT_RESULTS = {
    "WIN",
    "LOSS",
    "INCONCLUSIVE",
    "INVALIDATED",
    "STOPPED_FOR_GUARDRAIL",
    "CONFOUNDED",
}


EXPERIMENT_STATUSES = {state.value for state in ExperimentStatus}


EVIDENCE_QUALITY_STATES = {state.value for state in EvidenceQuality}


LEARNING_SCOPES = {state.value for state in LearningScope}


MATURITY_STATES = {state.value for state in MaturityState}


BUDGET_DELIVERY_STATES = {state.value for state in BudgetDeliveryState}


TARGET_CONSTRAINT_STATES = {state.value for state in TargetConstraintState}


EVENT_VOLUME_STATES = {state.value for state in EventVolumeState}


VALUE_SIGNAL_STATES = {state.value for state in ValueSignalState}


SPLIT_FEASIBILITY_STATES = {state.value for state in SplitFeasibilityState}


CALCULATION_EVIDENCE_TYPES = {state.value for state in CalculationEvidenceType}


class ContractError(ValueError):
    """Raised when input or ledger data violates a safety contract."""

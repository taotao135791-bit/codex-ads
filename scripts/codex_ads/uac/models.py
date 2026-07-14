"""Typed wire values for UAC diagnostics and validation helpers.

The deterministic engine intentionally keeps its existing string-valued JSON
contract. These enums and TypedDicts provide one typed definition for new code
without changing serialized values or requiring Python 3.11 ``StrEnum``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, TypedDict


class WireValue(str, Enum):
    """A JSON-compatible enum whose value is the existing wire string."""


class MeasurementState(WireValue):
    RELIABLE = "measurement_reliable"
    UNCERTAIN = "measurement_uncertain"
    UNRELIABLE = "measurement_unreliable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class LearningState(WireValue):
    LEARNABLE = "LEARNABLE"
    BORDERLINE = "BORDERLINE"
    INSUFFICIENT_EVENT_VOLUME = "INSUFFICIENT_EVENT_VOLUME"
    BUDGET_CONSTRAINED = "BUDGET_CONSTRAINED"
    TARGET_TOO_AGGRESSIVE = "TARGET_TOO_AGGRESSIVE"
    MEASUREMENT_UNRELIABLE = "MEASUREMENT_UNRELIABLE"
    CONVERSION_DELAY_NOT_MATURE = "CONVERSION_DELAY_NOT_MATURE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class FeasibilityState(WireValue):
    DIRECTLY_OPTIMIZABLE = "DIRECTLY_OPTIMIZABLE"
    LIMITED_INCREMENT_AVAILABLE = "LIMITED_INCREMENT_AVAILABLE"
    EXPERIMENT_AVAILABLE = "EXPERIMENT_AVAILABLE"
    DATA_BLOCKED = "DATA_BLOCKED"
    PERMISSION_BLOCKED = "PERMISSION_BLOCKED"
    TRACKING_BLOCKED = "TRACKING_BLOCKED"
    PRODUCT_FUNNEL_BLOCKED = "PRODUCT_FUNNEL_BLOCKED"
    LEARNING_BLOCKED = "LEARNING_BLOCKED"
    NO_ACTION_RECOMMENDED = "NO_ACTION_RECOMMENDED"


class PermissionClass(WireValue):
    OPTIMIZER_CAN_EXECUTE = "OPTIMIZER_CAN_EXECUTE"
    CLIENT_APPROVAL_REQUIRED = "CLIENT_APPROVAL_REQUIRED"
    CLIENT_DATA_REQUIRED = "CLIENT_DATA_REQUIRED"
    PRODUCT_DEPENDENCY = "PRODUCT_DEPENDENCY"
    TRACKING_DEPENDENCY = "TRACKING_DEPENDENCY"
    PLATFORM_LIMITATION = "PLATFORM_LIMITATION"
    NOT_ACTIONABLE = "NOT_ACTIONABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ExperimentStatus(WireValue):
    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    OBSERVING = "observing"
    COMPLETED = "completed"
    STOPPED = "stopped"
    CANCELLED = "cancelled"


class ExperimentOutcome(WireValue):
    WIN = "WIN"
    LOSS = "LOSS"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALIDATED = "INVALIDATED"
    STOPPED_FOR_GUARDRAIL = "STOPPED_FOR_GUARDRAIL"
    WAITING_FOR_MATURITY = "WAITING_FOR_MATURITY"
    INSUFFICIENT_VOLUME = "INSUFFICIENT_VOLUME"
    CONFOUNDED = "CONFOUNDED"


class EvidenceQuality(WireValue):
    PENDING = "pending"
    PLATFORM_ONLY = "platform_only"
    ACCOUNT_SPECIFIC = "account_specific"
    RECONCILED = "reconciled"
    INSUFFICIENT = "insufficient"
    NOT_EXECUTED = "not_executed"


class LearningScope(WireValue):
    ACCOUNT_SPECIFIC = "account_specific"
    PRODUCT_SPECIFIC = "product_specific"
    CREATIVE_SPECIFIC = "creative_specific"
    REUSABLE_HEURISTIC = "reusable_heuristic"


class MaturityState(WireValue):
    MATURE = "MATURE"
    PARTIALLY_MATURE = "PARTIALLY_MATURE"
    NOT_MATURE = "NOT_MATURE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class BudgetDeliveryState(WireValue):
    UNDER_DELIVERING = "UNDER_DELIVERING"
    NEAR_FULL_DELIVERY = "NEAR_FULL_DELIVERY"
    BUDGET_CONSTRAINED = "BUDGET_CONSTRAINED"
    NOT_BUDGET_CONSTRAINED = "NOT_BUDGET_CONSTRAINED"
    UNKNOWN = "UNKNOWN"


class TargetConstraintState(WireValue):
    LIKELY_TOO_TIGHT = "TARGET_LIKELY_TOO_TIGHT"
    LIKELY_TOO_LOOSE = "TARGET_LIKELY_TOO_LOOSE"
    NOT_PRIMARY = "TARGET_NOT_PRIMARY_CONSTRAINT"
    UNKNOWN = "UNKNOWN"


class EventVolumeState(WireValue):
    SUFFICIENT_AND_STABLE = "SUFFICIENT_AND_STABLE"
    SUFFICIENT_BUT_VOLATILE = "SUFFICIENT_BUT_VOLATILE"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


class ValueSignalState(WireValue):
    READY = "VALUE_SIGNAL_READY"
    BORDERLINE = "VALUE_SIGNAL_BORDERLINE"
    UNRELIABLE = "VALUE_SIGNAL_UNRELIABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class SplitFeasibilityState(WireValue):
    FEASIBLE = "SPLIT_FEASIBLE"
    BORDERLINE = "SPLIT_BORDERLINE"
    NOT_FEASIBLE = "SPLIT_NOT_FEASIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CalculationEvidenceType(WireValue):
    ACCOUNT_EVIDENCE = "ACCOUNT_EVIDENCE"
    BUSINESS_CONSTRAINT = "BUSINESS_CONSTRAINT"
    PLATFORM_GUIDANCE = "PLATFORM_GUIDANCE"
    HEURISTIC = "HEURISTIC"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class NormalizationIssue(TypedDict):
    field: str
    message: str


class NormalizationSource(TypedDict):
    label: str
    received_fields: list[str]
    field_map: dict[str, str]


class NormalizationResult(TypedDict):
    schema_version: str
    normalized: dict[str, Any]
    missing_fields: list[str]
    conversion_errors: list[NormalizationIssue]
    extras: dict[str, Any]
    source: NormalizationSource
    decision_made: bool


class RateMetric(TypedDict):
    numerator: int
    denominator: int
    rate: float | None

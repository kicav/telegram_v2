from dataclasses import dataclass

from ..core.enums import ActionType, TargetCoverage


@dataclass(slots=True)
class PrecheckResult:
    target_ids: set[int]
    coverage: TargetCoverage


@dataclass(slots=True)
class MigrationPlanSummary:
    total_source: int
    filtered: int
    already_target: int
    invalid: int
    ready: int
    not_in_target: int = 0
    action: ActionType = ActionType.INVITE

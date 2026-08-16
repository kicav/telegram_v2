from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from ..groups.models import GroupContext
from ..migration.models import MigrationPlanSummary, PrecheckResult


@dataclass(slots=True)
class StateSnapshot:
    active_account_id: int | None = None
    source_group: GroupContext | None = None
    source_account_id: int | None = None
    target_group: GroupContext | None = None
    target_account_id: int | None = None
    source_dataset_id: int | None = None
    precheck: PrecheckResult | None = None
    migration_job_id: int | None = None
    plan_summary: MigrationPlanSummary | None = None
    phone_code_hashes: dict[int, str] = field(default_factory=dict)


class StateStore:
    def __init__(self) -> None:
        self._state = StateSnapshot()
        self._lock = RLock()

    def snapshot(self) -> StateSnapshot:
        with self._lock:
            return StateSnapshot(
                active_account_id=self._state.active_account_id,
                source_group=self._state.source_group,
                source_account_id=self._state.source_account_id,
                target_group=self._state.target_group,
                target_account_id=self._state.target_account_id,
                source_dataset_id=self._state.source_dataset_id,
                precheck=self._state.precheck,
                migration_job_id=self._state.migration_job_id,
                plan_summary=self._state.plan_summary,
                phone_code_hashes=dict(self._state.phone_code_hashes),
            )

    def update(self, **values) -> None:
        with self._lock:
            for key, value in values.items():
                if not hasattr(self._state, key):
                    raise AttributeError(key)
                setattr(self._state, key, value)

    def set_phone_code_hash(self, account_id: int, phone_code_hash: str) -> None:
        with self._lock:
            self._state.phone_code_hashes[account_id] = phone_code_hash

    def pop_phone_code_hash(self, account_id: int) -> str | None:
        with self._lock:
            return self._state.phone_code_hashes.pop(account_id, None)

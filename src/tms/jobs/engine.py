from __future__ import annotations

from ..core.enums import JobState
from .repository import JobRepository
from .state_machine import validate_transition


class JobEngine:
    """Small state-transition facade backed by the persisted job state.

    Callers do not provide the previous state: it is loaded immediately before
    validation so stale UI/runtime state cannot authorize an invalid transition.
    """

    def __init__(self, repo: JobRepository) -> None:
        self.repo = repo

    def transition(self, job_id: int, new: JobState) -> None:
        row = self.repo.get(job_id)
        if row is None:
            raise KeyError(f"Unknown job id: {job_id}")
        old = JobState(str(row["state"]))
        validate_transition(old, new)
        self.repo.set_state(job_id, new)

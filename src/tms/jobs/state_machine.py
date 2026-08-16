from __future__ import annotations

from ..core.enums import JobState


ALLOWED: dict[JobState, set[JobState]] = {
    JobState.CREATED: {JobState.PREPARING, JobState.CANCELLED},
    JobState.PREPARING: {JobState.READY, JobState.FAILED, JobState.CANCELLED},
    JobState.READY: {JobState.RUNNING, JobState.CANCELLED},
    JobState.RUNNING: {
        JobState.PAUSED,
        JobState.WAITING_SERVER,
        JobState.COMPLETED,
        JobState.COMPLETED_WITH_ERRORS,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.PAUSED: {JobState.RUNNING, JobState.CANCELLED, JobState.FAILED},
    JobState.WAITING_SERVER: {
        JobState.RUNNING,
        JobState.PAUSED,
        JobState.CANCELLED,
        JobState.FAILED,
    },
    JobState.COMPLETED: set(),
    JobState.COMPLETED_WITH_ERRORS: set(),
    JobState.FAILED: set(),
    JobState.CANCELLED: set(),
}


def validate_transition(old: JobState, new: JobState) -> None:
    if old == new:
        return
    if new not in ALLOWED[old]:
        raise ValueError(f"Invalid job transition {old} -> {new}")

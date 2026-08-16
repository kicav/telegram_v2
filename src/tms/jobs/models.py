from dataclasses import dataclass
from ..core.enums import JobType, JobState


@dataclass(slots=True)
class Job:
    id: int | None
    job_type: JobType
    state: JobState
    account_id: int | None = None
    source_dataset_id: int | None = None
    target_group_id: int | None = None
    total: int = 0
    processed: int = 0
    success: int = 0
    skipped: int = 0
    failed: int = 0

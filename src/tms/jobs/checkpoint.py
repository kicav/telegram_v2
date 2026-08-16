from __future__ import annotations

from typing import Any

from .repository import JobRepository


class CheckpointService:
    def __init__(self, repo: JobRepository) -> None:
        self.repo = repo

    def save(self, job_id: int, **values: Any) -> None:
        self.repo.checkpoint(job_id, values)

    def load(self, job_id: int) -> dict[str, Any]:
        return self.repo.get_checkpoint(job_id)

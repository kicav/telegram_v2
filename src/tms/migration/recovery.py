from __future__ import annotations

from datetime import datetime, timezone

from ..core.enums import JobState, JobType
from ..jobs.repository import JobRepository


class RecoveryService:
    """Normalize persisted work after a process restart.

    Only member scans and member actions are resumable. Target pre-check is intentionally
    ephemeral: after a crash it is cancelled and will be rebuilt automatically the next
    time the user presses KIỂM TRA.
    """

    RESUMABLE_TYPES = {
        str(JobType.SCAN),
        str(JobType.MIGRATION),
        str(JobType.REMOVE),
    }
    ACTION_TYPES = {str(JobType.MIGRATION), str(JobType.REMOVE)}

    def __init__(self, jobs: JobRepository) -> None:
        self.jobs = jobs

    def recoverable_jobs(self) -> list[int]:
        return self.jobs.recoverable()

    def normalize_after_restart(self) -> list[int]:
        recovered: list[int] = []
        now = datetime.now(timezone.utc)
        for job_id in self.jobs.recoverable():
            row = self.jobs.get(job_id)
            if row is None:
                continue
            state = JobState(str(row["state"]))
            job_type = str(row["job_type"])

            # Target pre-check has no user-owned resumable state. Keeping a crashed
            # TARGET_SCAN paused would block the account forever while being hidden from
            # the simplified Activity table.
            if job_type == str(JobType.TARGET_SCAN):
                self.jobs.submit_set_state(
                    job_id,
                    JobState.CANCELLED,
                    checkpoint={
                        **self.jobs.get_checkpoint(job_id),
                        "recovered_after_restart": True,
                        "reason": "target_precheck_rebuild_required",
                    },
                    clear_waiting=True,
                ).result(timeout=10.0)
                recovered.append(job_id)
                continue

            # Only action jobs keep a still-active Telegram server wait after restart.
            if (
                job_type in self.ACTION_TYPES
                and state == JobState.WAITING_SERVER
                and row.get("waiting_until")
            ):
                try:
                    wait_until = datetime.fromisoformat(str(row["waiting_until"]))
                except ValueError:
                    wait_until = now
                if wait_until.tzinfo is None:
                    wait_until = wait_until.replace(tzinfo=timezone.utc)
                if wait_until > now:
                    recovered.append(job_id)
                    continue

            if job_type in self.RESUMABLE_TYPES and state in {
                JobState.RUNNING,
                JobState.WAITING_SERVER,
            }:
                self.jobs.submit_set_state(
                    job_id,
                    JobState.PAUSED,
                    checkpoint={
                        **self.jobs.get_checkpoint(job_id),
                        "recovered_after_restart": True,
                    },
                    clear_waiting=(state == JobState.WAITING_SERVER),
                ).result(timeout=10.0)
                recovered.append(job_id)
                continue

            # Any other interrupted non-resumable job must not keep an account locked.
            if job_type not in self.RESUMABLE_TYPES and state in {
                JobState.RUNNING,
                JobState.WAITING_SERVER,
                JobState.PAUSED,
            }:
                self.jobs.submit_set_state(
                    job_id,
                    JobState.CANCELLED,
                    checkpoint={
                        **self.jobs.get_checkpoint(job_id),
                        "recovered_after_restart": True,
                        "reason": "non_resumable_job",
                    },
                    clear_waiting=True,
                ).result(timeout=10.0)
            recovered.append(job_id)
        return recovered

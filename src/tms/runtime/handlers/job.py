from __future__ import annotations

from pathlib import Path

from ...core.enums import JobType
from ...core.events import DomainEvent
from .base import HandlerBase


class JobCommands(HandlerBase):
    """Persistent job history/recovery commands exposed to the simplified UI."""

    def __init__(self, context, workflow_commands, data_commands) -> None:
        super().__init__(context)
        self.workflow_commands = workflow_commands
        self.data_commands = data_commands

    def register(self, bus) -> None:
        bus.register("job.export_results", self.export_results)
        bus.register("job.export_log", self.export_log)
        bus.register("job.resume", self.resume_job)
        bus.register("job.stop", self.stop_job)

    def resume_job(self, job_id: int, interval_seconds: float) -> None:
        row = self.ctx.jobs.get(job_id)
        if row is None:
            raise ValueError("Không tìm thấy công việc")
        job_type = str(row["job_type"])
        if job_type in {str(JobType.MIGRATION), str(JobType.REMOVE)}:
            self.workflow_commands.resume_action(job_id, interval_seconds)
            return
        if job_type == str(JobType.SCAN):
            self.data_commands.resume_scan(job_id)
            return
        raise ValueError("Loại công việc này không hỗ trợ tiếp tục")

    def stop_job(self, job_id: int) -> None:
        row = self.ctx.jobs.get(job_id)
        if row is None:
            raise ValueError("Không tìm thấy công việc")
        job_type = str(row["job_type"])
        if job_type in {str(JobType.MIGRATION), str(JobType.REMOVE)}:
            self.workflow_commands.stop_action(job_id)
            return
        if job_type == str(JobType.SCAN):
            self.data_commands.stop_scan(job_id)
            return
        raise ValueError("Loại công việc này không hỗ trợ dừng")

    def export_log(self, job_id: int, path: str) -> None:
        if self.ctx.runtime.governor.performance_mode:
            self.ctx.runtime.events.publish(
                DomainEvent(
                    "BackgroundTaskDeferred",
                    {
                        "task": "log_export",
                        "reason": "Đang ưu tiên công việc thêm/xóa thành viên",
                    },
                )
            )
            return
        self._submit_worker(
            "job.export_log",
            lambda: self.ctx.import_export.export_job_log(job_id, Path(path)),
            lambda _x: self.ctx.runtime.events.publish(
                DomainEvent("LogExportCompleted", {"job_id": job_id, "path": path})
            ),
        )

    def export_results(self, job_id: int, path: str) -> None:
        if self.ctx.runtime.governor.performance_mode:
            self.ctx.runtime.events.publish(
                DomainEvent(
                    "BackgroundTaskDeferred",
                    {
                        "task": "result_export",
                        "reason": "Đang ưu tiên công việc thêm/xóa thành viên",
                    },
                )
            )
            return
        self._submit_worker(
            "job.export_results",
            lambda: self.ctx.import_export.export_job_results(job_id, Path(path)),
            lambda _x: self.ctx.runtime.events.publish(
                DomainEvent("ResultExportCompleted", {"job_id": job_id, "path": path})
            ),
        )

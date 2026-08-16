class JobController:
    def __init__(self, command_bus):
        self.commands = command_bus

    def export_results(self, job_id: int, path: str) -> None:
        self.commands.dispatch("job.export_results", job_id=job_id, path=path)

    def export_log(self, job_id: int, path: str) -> None:
        self.commands.dispatch("job.export_log", job_id=job_id, path=path)

    def resume_job(self, job_id: int, interval_seconds: float) -> None:
        self.commands.dispatch(
            "job.resume", job_id=job_id, interval_seconds=interval_seconds
        )

    def stop_job(self, job_id: int) -> None:
        self.commands.dispatch("job.stop", job_id=job_id)

    # Backward-compatible alias for older UI/tests.
    def resume_migration(self, job_id: int, interval_seconds: float) -> None:
        self.resume_job(job_id, interval_seconds)

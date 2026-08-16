from ...core.enums import ActionType


class WorkflowController:
    def __init__(self, command_bus):
        self.commands = command_bus

    def collect(self, account_id: int, reference: str, dataset_name: str) -> None:
        self.commands.dispatch(
            "workflow.collect",
            account_id=account_id,
            reference=reference,
            dataset_name=dataset_name,
        )

    def collect_group(self, account_id: int, group, dataset_name: str) -> None:
        self.commands.dispatch(
            "workflow.collect_group",
            account_id=account_id,
            group=group,
            dataset_name=dataset_name,
        )

    def load_joined_groups(self, account_id: int) -> None:
        self.commands.dispatch("source.joined_groups", account_id=account_id)

    def prepare(
        self,
        action: ActionType,
        account_id: int,
        dataset_id: int,
        target_reference: str,
        filter_spec,
    ) -> None:
        command = (
            "workflow.remove.prepare"
            if action == ActionType.REMOVE
            else "workflow.invite.prepare"
        )
        self.commands.dispatch(
            command,
            account_id=account_id,
            source_dataset_id=dataset_id,
            target_reference=target_reference,
            filter_spec=filter_spec,
        )

    def start(self, job_id: int, account_id: int, interval_seconds: float) -> None:
        self.commands.dispatch(
            "action.start",
            job_id=job_id,
            account_id=account_id,
            interval_seconds=interval_seconds,
        )

    def cancel_prepared(self, job_id: int) -> None:
        self.commands.dispatch("action.cancel_prepared", job_id=job_id)

    def pause(self, job_id: int) -> None:
        self.commands.dispatch("action.pause", job_id=job_id)

    def stop(self, job_id: int) -> None:
        self.commands.dispatch("action.stop", job_id=job_id)

    def resume(self, job_id: int, interval_seconds: float) -> None:
        self.commands.dispatch(
            "action.resume", job_id=job_id, interval_seconds=interval_seconds
        )

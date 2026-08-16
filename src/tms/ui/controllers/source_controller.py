class SourceController:
    def __init__(self, command_bus):
        self.commands = command_bus

    def resolve(self, account_id: int, reference: str) -> None:
        self.commands.dispatch("source.resolve", account_id=account_id, reference=reference)

    def joined_groups(self, account_id: int) -> None:
        self.commands.dispatch("source.joined_groups", account_id=account_id)

    def select_group(self, account_id: int, group) -> None:
        self.commands.dispatch(
            "source.select_group", account_id=account_id, group=group
        )

    def scan(self, account_id: int, dataset_name: str) -> None:
        self.commands.dispatch(
            "source.scan", account_id=account_id, dataset_name=dataset_name
        )

    def cancel_scan(self, job_id: int) -> None:
        self.commands.dispatch("source.cancel_scan", job_id=job_id)

    def import_file(self, path: str, name: str, account_id: int | None) -> None:
        self.commands.dispatch(
            "dataset.import", path=path, name=name, account_id=account_id
        )

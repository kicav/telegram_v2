class MemberController:
    def __init__(self, command_bus):
        self.commands = command_bus

    def select_dataset(self, dataset_id: int) -> None:
        self.commands.dispatch("dataset.select", dataset_id=dataset_id)

    def combine(self, name: str, a_id: int, b_id: int, operation: str) -> None:
        self.commands.dispatch(
            "dataset.combine", name=name, a_id=a_id, b_id=b_id, operation=operation
        )

    def export(self, dataset_id: int, path: str, account_id: int | None = None) -> None:
        self.commands.dispatch(
            "dataset.export", dataset_id=dataset_id, path=path, account_id=account_id
        )

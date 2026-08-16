class AccountController:
    def __init__(self, command_bus):
        self.commands = command_bus

    def update_settings(self, api_id: int, api_hash: str) -> None:
        self.commands.dispatch("settings.update", api_id=api_id, api_hash=api_hash)

    def add(self, phone: str) -> None:
        self.commands.dispatch("account.add", phone=phone)

    def select(self, account_id: int) -> None:
        self.commands.dispatch("account.select", account_id=account_id)

    def connect(self, account_id: int) -> None:
        self.commands.dispatch("account.connect", account_id=account_id)

    def send_code(self, account_id: int) -> None:
        self.commands.dispatch("auth.send_code", account_id=account_id)

    def sign_in(self, account_id: int, code: str, password: str | None = None) -> None:
        self.commands.dispatch(
            "auth.sign_in", account_id=account_id, code=code, password=password
        )

    def enable(self, account_id: int, enabled: bool) -> None:
        self.commands.dispatch("account.enable", account_id=account_id, enabled=enabled)

    def delete(self, account_id: int) -> None:
        self.commands.dispatch("account.delete", account_id=account_id)

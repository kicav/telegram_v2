from dataclasses import dataclass
from ..core.enums import AccountState


@dataclass(slots=True)
class Account:
    id: int | None
    phone: str
    session_path: str
    telegram_user_id: int | None = None
    username: str | None = None
    display_name: str | None = None
    status: AccountState = AccountState.DISCONNECTED
    enabled: bool = True

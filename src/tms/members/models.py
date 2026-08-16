from dataclasses import dataclass


@dataclass(slots=True)
class Member:
    telegram_user_id: int | None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    bot: bool = False
    deleted: bool = False
    activity_status: str | None = None
    last_seen: str | None = None
    access_hash: int | None = None

    @property
    def identity_key(self) -> tuple[str, str] | None:
        if self.telegram_user_id is not None:
            return ("id", str(self.telegram_user_id))
        if self.username:
            return ("username", self.username.lower().lstrip("@"))
        return None

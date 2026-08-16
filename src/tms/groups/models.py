from dataclasses import dataclass


@dataclass(slots=True)
class GroupContext:
    telegram_id: int
    access_hash: int | None
    title: str
    username: str | None
    type: str
    is_member: bool = False
    is_admin: bool = False
    can_read: bool = False
    can_invite: bool = False
    can_send: bool = False
    resolved_at: str | None = None
    local_group_id: int | None = None
    can_remove: bool = False

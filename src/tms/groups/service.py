from __future__ import annotations

import re

from .models import GroupContext


_INVITE_PATTERNS = ("joinchat/", "+")


def normalize_group_reference(value: str) -> str:
    """Normalize public references while preserving private invite links."""
    raw = value.strip()
    if not raw:
        raise ValueError("Group reference is required")
    lowered = raw.lower()
    if "joinchat/" in lowered or "t.me/+" in lowered:
        return raw
    raw = re.sub(r"^https?://", "", raw, flags=re.I)
    raw = re.sub(r"^(www\.)?t\.me/", "", raw, flags=re.I)
    if raw.startswith("@"):
        raw = raw[1:]
    return raw.strip().strip("/")


def invite_hash(reference: str) -> str | None:
    raw = reference.strip()
    lowered = raw.lower()
    if "joinchat/" in lowered:
        return raw.rsplit("joinchat/", 1)[-1].split("?", 1)[0].strip("/")
    marker = "t.me/+"
    if marker in lowered:
        index = lowered.rfind(marker)
        return raw[index + len(marker) :].split("?", 1)[0].strip("/")
    if raw.startswith("+"):
        return raw[1:].split("?", 1)[0].strip("/")
    return None


class GroupService:
    def __init__(self, gateway: object) -> None:
        self.gateway = gateway

    async def resolve(self, account_id: int, reference: str) -> GroupContext:
        return await self.gateway.resolve_group(account_id, normalize_group_reference(reference))

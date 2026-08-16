from __future__ import annotations

from collections.abc import AsyncIterator

from ..groups.models import GroupContext
from ..members.models import Member


class FakeTelegramGateway:
    def __init__(self, pages=None, invite_effects=None, remove_effects=None) -> None:
        self.pages = pages or []
        self.invite_effects = list(invite_effects or [])
        self.remove_effects = list(remove_effects or [])
        self.invites: list[int | None] = []
        self.removes: list[int | None] = []
        self.resolve_calls = 0
        self.participant_page_requests = 0
        self.join_calls = 0
        self.leave_calls = 0

    async def resolve_group(self, account_id: int, reference: str) -> GroupContext:
        self.resolve_calls += 1
        return GroupContext(
            telegram_id=100,
            access_hash=10,
            title=reference,
            username=reference,
            type="Channel",
            is_member=True,
            is_admin=True,
            can_read=True,
            can_invite=True,
            can_send=True,
            can_remove=True,
        )

    async def get_joined_groups(self, account_id: int) -> list[GroupContext]:
        return []

    async def iter_participant_pages(
        self,
        account_id: int,
        group: GroupContext,
        offset: int,
        limit: int,
    ) -> AsyncIterator[list[Member]]:
        start_page = 0
        consumed = 0
        for index, page in enumerate(self.pages):
            if consumed + len(page) <= offset:
                consumed += len(page)
                start_page = index + 1
                continue
            break
        for page in self.pages[start_page:]:
            self.participant_page_requests += 1
            yield page

    @staticmethod
    def _apply_effect(effects: list, default=None) -> None:
        if not effects:
            return default
        effect = effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        if callable(effect):
            effect()
        return default

    async def invite_user(
        self,
        account_id: int,
        target: GroupContext,
        member: Member,
    ) -> None:
        self.invites.append(member.telegram_user_id)
        self._apply_effect(self.invite_effects)

    async def remove_user(
        self,
        account_id: int,
        target: GroupContext,
        member: Member,
    ) -> None:
        self.removes.append(member.telegram_user_id)
        self._apply_effect(self.remove_effects)

    async def join_group(self, account_id: int, reference: str) -> GroupContext:
        self.join_calls += 1
        return await self.resolve_group(account_id, reference)

    async def leave_group(self, account_id: int, group: GroupContext) -> None:
        self.leave_calls += 1

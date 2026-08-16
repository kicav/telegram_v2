from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from ..accounts.repository import AccountRepository
from ..groups.models import GroupContext
from ..groups.service import invite_hash
from ..members.models import Member
from ..members.normalizer import normalize_member
from .client_manager import ClientManager
from .peer_cache import CachedPeer, PeerCache


class TelethonGateway:
    """Production TelegramGateway backed by Telethon 1.44.x.

    Telethon imports are lazy so local unit tests can validate the whole core without a
    network dependency. Every public coroutine is expected to execute on NetworkRuntime.
    """

    def __init__(
        self,
        clients: ClientManager,
        accounts: AccountRepository,
        peers: PeerCache,
    ) -> None:
        self.clients = clients
        self.accounts = accounts
        self.peers = peers

    def _session(self, account_id: int) -> str:
        account = self.accounts.get(account_id)
        if account is None:
            raise KeyError(f"Unknown account id: {account_id}")
        if not account.enabled:
            raise RuntimeError("Selected account is disabled")
        return account.session_path

    async def _client(self, account_id: int) -> Any:
        return await self.clients.get(account_id, self._session(account_id))

    @staticmethod
    def _input_channel(group: GroupContext) -> Any:
        from telethon.tl import types

        if group.access_hash is None:
            raise ValueError("Target/source channel has no cached access hash")
        return types.InputChannel(group.telegram_id, group.access_hash)

    @staticmethod
    def _group_context(entity: Any, *, is_member_override: bool | None = None) -> GroupContext:
        admin_rights = getattr(entity, "admin_rights", None)
        default_banned = getattr(entity, "default_banned_rights", None)
        creator = bool(getattr(entity, "creator", False))
        left = bool(getattr(entity, "left", False))
        is_member = not left if is_member_override is None else is_member_override
        entity_type = type(entity).__name__
        is_chat = entity_type.lower() == "chat"
        is_broadcast = bool(getattr(entity, "broadcast", False))
        username = getattr(entity, "username", None)
        access_hash = getattr(entity, "access_hash", None)
        default_allows_invites = not bool(
            getattr(default_banned, "invite_users", False)
        )
        member_can_invite = (
            is_member and not is_broadcast and default_allows_invites
        )
        can_invite = (
            creator
            or bool(getattr(admin_rights, "invite_users", False))
            or member_can_invite
            or (is_chat and is_member and default_banned is None)
        )
        can_remove = creator or bool(getattr(admin_rights, "ban_users", False))
        # Public groups/channels can often be inspected by username without joining;
        # private invite links are handled separately and require membership first.
        can_read = is_member or bool(username)
        return GroupContext(
            telegram_id=int(entity.id),
            access_hash=(int(access_hash) if access_hash is not None else None),
            title=(
                getattr(entity, "title", None)
                or getattr(entity, "first_name", None)
                or str(entity.id)
            ),
            username=username,
            type=entity_type,
            is_member=is_member,
            is_admin=creator or admin_rights is not None,
            can_read=can_read,
            can_invite=can_invite,
            can_send=is_member,
            resolved_at=datetime.now(timezone.utc).isoformat(),
            can_remove=can_remove,
        )

    async def resolve_group(self, account_id: int, reference: str) -> GroupContext:
        client = await self._client(account_id)
        token = invite_hash(reference)
        if token:
            from telethon.tl import functions

            invite = await client(functions.messages.CheckChatInviteRequest(hash=token))
            entity = getattr(invite, "chat", None)
            if entity is None:
                title = getattr(invite, "title", None) or "Private invite"
                raise RuntimeError(
                    f"Link mời '{title}' hợp lệ nhưng tài khoản phải tham gia nhóm trước khi có thể đọc thành viên"
                )
            group = self._group_context(entity, is_member_override=True)
        else:
            entity = await client.get_entity(reference)
            group = self._group_context(entity)

        persist = self.peers.put(
            CachedPeer(
                account_id=account_id,
                peer_id=group.telegram_id,
                peer_type=group.type,
                access_hash=group.access_hash,
                username=group.username,
                title=group.title,
            )
        )
        if persist is not None:
            await asyncio.wrap_future(persist)
        return group

    async def get_joined_groups(self, account_id: int) -> list[GroupContext]:
        client = await self._client(account_id)
        groups: list[GroupContext] = []
        peers: list[CachedPeer] = []
        async for dialog in client.iter_dialogs():
            if not (dialog.is_group or dialog.is_channel):
                continue
            entity = dialog.entity
            group = self._group_context(entity, is_member_override=True)
            peers.append(
                CachedPeer(
                    account_id=account_id,
                    peer_id=group.telegram_id,
                    peer_type=group.type,
                    access_hash=group.access_hash,
                    username=group.username,
                    title=group.title,
                )
            )
            groups.append(group)
        if peers:
            await asyncio.wrap_future(self.peers.submit_persist_many(peers))
        return groups

    async def iter_participant_pages(
        self,
        account_id: int,
        group: GroupContext,
        offset: int,
        limit: int,
    ) -> AsyncIterator[list[Member]]:
        client = await self._client(account_id)
        group_type = group.type.lower()
        if group_type == "chat":
            if offset > 0:
                return
            from telethon.tl import functions

            result = await client(functions.messages.GetFullChatRequest(chat_id=group.telegram_id))
            users = list(getattr(result, "users", []))
            if users:
                yield [normalize_member(raw) for raw in users]
            return

        from telethon.tl import functions, types

        entity = self._input_channel(group)
        current = max(0, offset)
        page_limit = max(1, min(limit, 200))
        while True:
            result = await client(
                functions.channels.GetParticipantsRequest(
                    channel=entity,
                    filter=types.ChannelParticipantsSearch(""),
                    offset=current,
                    limit=page_limit,
                    hash=0,
                )
            )
            users = list(getattr(result, "users", []))
            if not users:
                return
            yield [normalize_member(raw) for raw in users]
            current += len(users)
            if len(users) < page_limit:
                return

    async def invite_user(
        self,
        account_id: int,
        target: GroupContext,
        member: Member,
    ) -> None:
        """Invite exactly one candidate with no target/member resolve RPC in the hot path."""
        if member.telegram_user_id is None:
            raise ValueError("Member has no Telegram user id")
        if member.access_hash is None:
            raise ValueError("Missing account-scoped cached access hash for candidate")

        client = await self._client(account_id)
        from telethon.tl import functions, types

        input_user = types.InputUser(member.telegram_user_id, member.access_hash)
        if target.type.lower() == "chat":
            await client(
                functions.messages.AddChatUserRequest(
                    chat_id=target.telegram_id,
                    user_id=input_user,
                    fwd_limit=0,
                )
            )
            return

        target_input = self._input_channel(target)
        await client(functions.channels.InviteToChannelRequest(target_input, [input_user]))

    async def remove_user(
        self,
        account_id: int,
        target: GroupContext,
        member: Member,
    ) -> None:
        """Remove one member while allowing a future voluntary rejoin.

        For channels/supergroups Telegram implements a kick as ban + unban. Both RPCs
        use cached InputChannel/InputUser objects, so no entity resolution happens in
        the action hot path.
        """
        if member.telegram_user_id is None:
            raise ValueError("Member has no Telegram user id")
        if member.access_hash is None:
            raise ValueError("Missing account-scoped cached access hash for candidate")

        client = await self._client(account_id)
        from telethon.tl import functions, types

        input_user = types.InputUser(member.telegram_user_id, member.access_hash)
        if target.type.lower() == "chat":
            await client(
                functions.messages.DeleteChatUserRequest(
                    chat_id=target.telegram_id,
                    user_id=input_user,
                    revoke_history=False,
                )
            )
            return

        target_input = self._input_channel(target)
        # Telethon's public kick helper implements the channel/supergroup kick as
        # ban + unban. Passing cached InputChannel/InputUser keeps entity resolution
        # out of the member-action hot path and avoids us owning a partially-unbanned
        # two-request sequence here.
        await client.kick_participant(target_input, input_user)

    async def join_group(self, account_id: int, reference: str) -> GroupContext:
        client = await self._client(account_id)
        token = invite_hash(reference)
        if token:
            from telethon.tl import functions

            result = await client(functions.messages.ImportChatInviteRequest(hash=token))
            chats = list(getattr(result, "chats", []))
            if chats:
                group = self._group_context(chats[0], is_member_override=True)
                persist = self.peers.put(
                    CachedPeer(
                        account_id,
                        group.telegram_id,
                        group.type,
                        group.access_hash,
                        group.username,
                        group.title,
                    )
                )
                if persist is not None:
                    await asyncio.wrap_future(persist)
                return group
            raise RuntimeError("Joined invite but Telegram returned no chat entity")

        entity = await client.get_entity(reference)
        from telethon.tl import functions

        if type(entity).__name__.lower() == "chat":
            return self._group_context(entity, is_member_override=True)
        await client(functions.channels.JoinChannelRequest(entity))
        return await self.resolve_group(account_id, reference)

    async def leave_group(self, account_id: int, group: GroupContext) -> None:
        client = await self._client(account_id)
        from telethon.tl import functions

        if group.type.lower() == "chat":
            # Utility path only: resolving the current user here is allowed because this
            # operation is outside the migration hot path. Raw TL requests require an
            # InputUser rather than a convenience string.
            me = await client.get_input_entity("me")
            await client(
                functions.messages.DeleteChatUserRequest(
                    chat_id=group.telegram_id,
                    user_id=me,
                    revoke_history=False,
                )
            )
            return
        await client(functions.channels.LeaveChannelRequest(self._input_channel(group)))

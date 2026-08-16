from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..accounts.repository import AccountRepository
from ..core.enums import AccountState
from .client_manager import ClientManager


@dataclass(slots=True)
class AuthIdentity:
    telegram_user_id: int | None
    username: str | None
    display_name: str | None


class AuthService:
    """OTP/2FA session authentication executed only on the Telegram runtime."""

    def __init__(
        self,
        clients: ClientManager,
        accounts: AccountRepository,
        session_lookup: Callable[[int], str],
    ) -> None:
        self.clients = clients
        self.accounts = accounts
        self.session_lookup = session_lookup

    async def send_code(self, account_id: int, phone: str) -> str:
        await self._set_account_state(account_id, AccountState.CONNECTING)
        try:
            client = await self.clients.get(account_id, self.session_lookup(account_id))
            if await client.is_user_authorized():
                await self.refresh_identity(account_id)
                return ""
            sent = await client.send_code_request(phone)
        except Exception as exc:
            await self._set_account_state(account_id, AccountState.ERROR, str(exc))
            raise
        await self._set_account_state(account_id, AccountState.AUTH_REQUIRED)
        return str(sent.phone_code_hash)

    async def sign_in(
        self,
        account_id: int,
        phone: str,
        code: str,
        phone_code_hash: str,
        password: str | None = None,
    ) -> AuthIdentity:
        client = await self.clients.get(account_id, self.session_lookup(account_id))
        try:
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash,
            )
        except Exception as exc:
            name = type(exc).__name__.lower()
            if "sessionpasswordneeded" in name:
                if not password:
                    await self._set_account_state(
                        account_id,
                        AccountState.AUTH_REQUIRED,
                        "Cần nhập mật khẩu 2FA của Telegram",
                    )
                    raise RuntimeError("Cần nhập mật khẩu 2FA của Telegram") from exc
                try:
                    await client.sign_in(password=password)
                except Exception as password_exc:
                    await self._set_account_state(
                        account_id,
                        AccountState.AUTH_REQUIRED,
                        str(password_exc),
                    )
                    raise
            else:
                state = (
                    AccountState.AUTH_REQUIRED
                    if any(token in name for token in ("phonecode", "password", "auth"))
                    else AccountState.ERROR
                )
                await self._set_account_state(account_id, state, str(exc))
                raise
        return await self.refresh_identity(account_id)

    async def connect_existing(self, account_id: int) -> AuthIdentity | None:
        await self._set_account_state(account_id, AccountState.CONNECTING)
        try:
            client = await self.clients.get(account_id, self.session_lookup(account_id))
            if not await client.is_user_authorized():
                await self._set_account_state(account_id, AccountState.AUTH_REQUIRED)
                return None
            return await self.refresh_identity(account_id)
        except Exception as exc:
            await self._set_account_state(account_id, AccountState.ERROR, str(exc))
            raise

    async def refresh_identity(self, account_id: int) -> AuthIdentity:
        client = await self.clients.get(account_id, self.session_lookup(account_id))
        me: Any = await client.get_me()
        if me is None:
            raise RuntimeError("Telegram session has no authenticated user")
        first = getattr(me, "first_name", None) or ""
        last = getattr(me, "last_name", None) or ""
        display_name = " ".join(part for part in (first, last) if part).strip() or None
        identity = AuthIdentity(
            telegram_user_id=(int(me.id) if getattr(me, "id", None) is not None else None),
            username=getattr(me, "username", None),
            display_name=display_name,
        )
        await self._await_writer(
            self.accounts.submit_update_identity(
                account_id,
                identity.telegram_user_id,
                identity.username,
                identity.display_name,
            )
        )
        return identity

    async def _set_account_state(
        self,
        account_id: int,
        state: AccountState,
        error: str | None = None,
    ) -> None:
        await self._await_writer(self.accounts.submit_set_state(account_id, state, error))

    @staticmethod
    async def _await_writer(future: Any) -> Any:
        return await asyncio.wrap_future(future)

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ...core.constants import MAX_INVITE_INTERVAL_SECONDS, MIN_INVITE_INTERVAL_SECONDS
from ...core.enums import JobState
from ...core.events import DomainEvent
from .base import HandlerBase


class AccountCommands(HandlerBase):
    def register(self, bus) -> None:
        bus.register("settings.update", self.update_settings)
        bus.register("settings.update_interval", self.update_interval_setting)
        bus.register("account.add", self.add_account)
        bus.register("account.enable", self.enable_account)
        bus.register("account.delete", self.delete_account)
        bus.register("account.select", self.select_account)
        bus.register("account.connect", self.connect_account)
        bus.register("auth.send_code", self.send_code)
        bus.register("auth.sign_in", self.sign_in)

    def update_settings(
        self,
        api_id: int,
        api_hash: str,
        interval_seconds: float | None = None,
    ) -> None:
        if api_id <= 0 or not api_hash.strip():
            raise ValueError("API ID và API Hash là bắt buộc")
        if self.ctx.jobs.has_active_telegram_work():
            raise RuntimeError(
                "Hãy hoàn thành hoặc dừng các công việc Telegram đang hoạt động trước khi đổi Telegram API."
            )

        async def apply_credentials() -> None:
            await self.ctx.clients.close_all()
            self.ctx.clients.update_credentials(api_id, api_hash.strip())

        def save_settings() -> None:
            self.ctx.settings.api_id = api_id
            self.ctx.settings.api_hash = api_hash.strip()
            if interval_seconds is not None:
                value = float(interval_seconds)
                if not MIN_INVITE_INTERVAL_SECONDS <= value <= MAX_INVITE_INTERVAL_SECONDS:
                    raise ValueError("Khoảng nghỉ phải nằm trong 3–8 giây")
                self.ctx.settings.invite_interval_seconds = value
            self.ctx.settings.save(self.ctx.paths)

        def credentials_applied(_result: Any) -> None:
            self._submit_worker(
                "settings.update",
                save_settings,
                lambda _saved: self.ctx.runtime.events.publish(
                    DomainEvent("SettingsChanged", {})
                ),
            )

        self._submit_network("settings.update", apply_credentials(), credentials_applied)

    def update_interval_setting(self, interval_seconds: float) -> None:
        value = float(interval_seconds)
        if not MIN_INVITE_INTERVAL_SECONDS <= value <= MAX_INVITE_INTERVAL_SECONDS:
            raise ValueError("Khoảng nghỉ phải nằm trong 3–8 giây")

        def save() -> None:
            self.ctx.settings.invite_interval_seconds = value
            self.ctx.settings.save(self.ctx.paths)

        self._submit_worker(
            "settings.update_interval",
            save,
            lambda _x: self.ctx.runtime.events.publish(
                DomainEvent("SettingsChanged", {"invite_interval_seconds": value})
            ),
        )

    def add_account(self, phone: str) -> None:
        def done(account) -> None:
            self.ctx.runtime.events.publish(
                DomainEvent("AccountsChanged", {"account_id": account.id})
            )

        self._submit_worker("account.add", lambda: self.ctx.account_service.add(phone), done)

    def enable_account(self, account_id: int, enabled: bool) -> None:
        if not enabled and self.ctx.jobs.has_nonterminal_jobs(account_id):
            raise RuntimeError("Hãy dừng/hoàn thành công việc của tài khoản trước khi tắt")

        self._submit_worker(
            "account.enable",
            lambda: self.ctx.account_service.enable(account_id, enabled),
            lambda _result: self.ctx.runtime.events.publish(
                DomainEvent("AccountsChanged", {"account_id": account_id})
            ),
        )

    def delete_account(self, account_id: int) -> None:
        if self.ctx.accounts.get(account_id) is None:
            raise ValueError("Không tìm thấy tài khoản")
        if self.ctx.jobs.has_nonterminal_jobs(account_id):
            raise RuntimeError("Tài khoản còn công việc chưa hoàn tất")

        async def disconnect_then_delete() -> None:
            await self.ctx.clients.disconnect(account_id)

        def after_disconnect(_result: Any) -> None:
            self._submit_worker(
                "account.delete",
                lambda: self.ctx.account_service.delete(account_id),
                lambda _x: self.ctx.runtime.events.publish(
                    DomainEvent("AccountsChanged", {"account_id": account_id})
                ),
            )

        self._submit_network("account.delete", disconnect_then_delete(), after_disconnect)

    def select_account(self, account_id: int) -> None:
        self.ctx.state.update(active_account_id=account_id)
        self.ctx.runtime.events.publish(
            DomainEvent("ActiveAccountChanged", {"account_id": account_id})
        )

    def _guard_not_busy(self, account_id: int) -> None:
        active = self.ctx.jobs.active_job_for_account(account_id)
        if active and str(active["state"]) in {
            str(JobState.RUNNING),
            str(JobState.WAITING_SERVER),
        }:
            raise RuntimeError(
                "Tài khoản đang được một công việc sử dụng. Không cần kết nối/reset lại trong lúc này."
            )

    def connect_account(self, account_id: int) -> None:
        self._require_enabled_account(account_id)
        self._guard_not_busy(account_id)
        self._submit_network(
            "account.connect",
            self.ctx.auth.connect_existing(account_id),
            lambda identity: self.ctx.runtime.events.publish(
                DomainEvent(
                    "AccountConnected",
                    {
                        "account_id": account_id,
                        "authorized": identity is not None,
                        "identity": asdict(identity) if identity else None,
                    },
                )
            ),
        )

    def send_code(self, account_id: int) -> None:
        account = self._require_enabled_account(account_id)
        self._guard_not_busy(account_id)

        def done(code_hash: str) -> None:
            if code_hash:
                self.ctx.state.set_phone_code_hash(account_id, code_hash)
            self.ctx.runtime.events.publish(
                DomainEvent(
                    "AuthCodeSent",
                    {"account_id": account_id, "already_authorized": not bool(code_hash)},
                )
            )

        self._submit_network(
            "auth.send_code",
            self.ctx.auth.send_code(account_id, account.phone),
            done,
        )

    def sign_in(self, account_id: int, code: str, password: str | None = None) -> None:
        account = self._require_enabled_account(account_id)
        code_hash = self.ctx.state.snapshot().phone_code_hashes.get(account_id)
        if not code_hash:
            raise ValueError("Hãy gửi mã OTP trước khi đăng nhập")

        def done(identity) -> None:
            self.ctx.state.pop_phone_code_hash(account_id)
            self.ctx.runtime.events.publish(
                DomainEvent(
                    "AccountAuthenticated",
                    {"account_id": account_id, "identity": asdict(identity)},
                )
            )

        self._submit_network(
            "auth.sign_in",
            self.ctx.auth.sign_in(account_id, account.phone, code, code_hash, password),
            done,
        )

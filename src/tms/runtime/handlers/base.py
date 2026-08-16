from __future__ import annotations

from typing import Any, Callable

from ...core.events import DomainEvent


class HandlerBase:
    def __init__(self, context) -> None:
        self.ctx = context

    def _publish_failure(self, command: str, exc: BaseException) -> None:
        self.ctx.runtime.events.publish(
            DomainEvent(
                "CommandFailed",
                {"command": command, "error": str(exc), "type": type(exc).__name__},
            )
        )

    def _submit_worker(
        self,
        command: str,
        func: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
    ) -> None:
        future = self.ctx.runtime.workers.submit(func)

        def done(completed) -> None:
            try:
                result = completed.result()
                if on_success is not None:
                    on_success(result)
            except BaseException as exc:
                self._publish_failure(command, exc)

        future.add_done_callback(done)

    def _submit_network(
        self,
        command: str,
        coro,
        on_success: Callable[[Any], None] | None = None,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        try:
            future = self.ctx.runtime.network.submit(coro)
        except BaseException as exc:
            close = getattr(coro, "close", None)
            if callable(close):
                close()
            self._publish_failure(command, exc)
            if on_finished is not None:
                on_finished()
            return

        def done(completed) -> None:
            try:
                result = completed.result()
                if on_success is not None:
                    on_success(result)
            except BaseException as exc:
                self._publish_failure(command, exc)
            finally:
                if on_finished is not None:
                    on_finished()

        future.add_done_callback(done)

    def _require_enabled_account(self, account_id: int):
        account = self.ctx.accounts.get(account_id)
        if account is None:
            raise ValueError("Không tìm thấy tài khoản")
        if not account.enabled:
            raise RuntimeError("Tài khoản đang bị tắt")
        return account

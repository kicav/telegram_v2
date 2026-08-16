from __future__ import annotations

from ..core.clock import Clock, RealClock
from ..core.constants import (
    DEFAULT_INVITE_INTERVAL_SECONDS,
    MAX_INVITE_INTERVAL_SECONDS,
    MIN_INVITE_INTERVAL_SECONDS,
)


class InviteScheduler:
    """Monotonic attempt scheduler. Server wait always overrides local cadence."""

    def __init__(
        self,
        interval_seconds: float = DEFAULT_INVITE_INTERVAL_SECONDS,
        clock: Clock | None = None,
    ) -> None:
        if not MIN_INVITE_INTERVAL_SECONDS <= interval_seconds <= MAX_INVITE_INTERVAL_SECONDS:
            raise ValueError("Invite interval must be between 3 and 8 seconds")
        self.interval = interval_seconds
        self.clock = clock or RealClock()
        self._last_attempt: float | None = None
        self._server_wait_until = 0.0

    def apply_server_wait(self, seconds: float) -> None:
        self._server_wait_until = max(
            self._server_wait_until,
            self.clock.monotonic() + max(0.0, seconds),
        )

    def server_wait_remaining(self) -> float:
        return max(0.0, self._server_wait_until - self.clock.monotonic())

    def remaining_delay(self) -> float:
        now = self.clock.monotonic()
        local_next = (
            self._last_attempt + self.interval
            if self._last_attempt is not None
            else now
        )
        return max(0.0, max(local_next, self._server_wait_until) - now)

    async def wait_before_next(self) -> None:
        await self.clock.sleep(self.remaining_delay())

    def mark_attempt(self) -> None:
        self._last_attempt = self.clock.monotonic()

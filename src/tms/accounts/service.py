from __future__ import annotations

from pathlib import Path
import re

from ..core.enums import AccountState
from .models import Account
from .repository import AccountRepository


class AccountService:
    def __init__(self, repo: AccountRepository, sessions_dir: Path) -> None:
        self.repo = repo
        self.sessions_dir = sessions_dir

    @staticmethod
    def normalize_phone(phone: str) -> str:
        value = phone.strip().replace(" ", "")
        if not re.fullmatch(r"\+?\d{6,20}", value):
            raise ValueError("Số điện thoại phải có 6–20 chữ số và có thể bắt đầu bằng dấu +")
        return value if value.startswith("+") else f"+{value}"

    def add(self, phone: str) -> Account:
        normalized = self.normalize_phone(phone)
        safe = "".join(char for char in normalized if char.isdigit())
        session = self.sessions_dir / f"account_{safe}.session"
        account = Account(
            id=None,
            phone=normalized,
            session_path=str(session),
            status=AccountState.DISCONNECTED,
        )
        account.id = self.repo.create(account)
        return account

    def enable(self, account_id: int, enabled: bool) -> None:
        self.repo.submit_set_enabled(account_id, enabled).result(timeout=10.0)

    def delete(self, account_id: int, *, delete_session: bool = True) -> None:
        account = self.repo.get(account_id)
        if account is None:
            return
        self.repo.submit_delete(account_id).result(timeout=10.0)
        if delete_session:
            path = Path(account.session_path)
            for candidate in (
                path,
                Path(f"{path}-journal"),
                Path(f"{path}-wal"),
                Path(f"{path}-shm"),
            ):
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    # The database row is already removed; stale session sidecars are
                    # harmless and can be cleaned on the next manual maintenance pass.
                    pass

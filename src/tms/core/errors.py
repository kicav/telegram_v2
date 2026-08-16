from dataclasses import dataclass
from .enums import InviteResultCode


@dataclass(slots=True)
class DomainError(Exception):
    code: InviteResultCode
    message: str
    wait_seconds: int | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

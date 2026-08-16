from dataclasses import dataclass

from ..core.enums import InviteResultCode, MigrationItemState
from ..core.errors import DomainError


@dataclass(slots=True)
class ClassifiedResult:
    state: MigrationItemState
    retry: bool = False
    pause_job: bool = False
    wait_seconds: int | None = None


class ResultClassifier:
    def classify(self, error: DomainError | None) -> ClassifiedResult:
        if error is None:
            return ClassifiedResult(MigrationItemState.SUCCESS)
        if error.code in {InviteResultCode.ALREADY_MEMBER, InviteResultCode.NOT_MEMBER}:
            return ClassifiedResult(MigrationItemState.SKIPPED)
        if error.code in {
            InviteResultCode.PRIVACY,
            InviteResultCode.NOT_ELIGIBLE,
            InviteResultCode.INVALID_USER,
        }:
            return ClassifiedResult(MigrationItemState.SKIPPED)
        if error.code in {
            InviteResultCode.PERMISSION,
            InviteResultCode.AUTH,
            InviteResultCode.RATE_LIMIT_INDEFINITE,
        }:
            return ClassifiedResult(MigrationItemState.FAILED, pause_job=True)
        if error.code == InviteResultCode.RATE_LIMIT:
            return ClassifiedResult(
                MigrationItemState.RETRY,
                retry=True,
                wait_seconds=error.wait_seconds or 0,
            )
        if error.code in {
            InviteResultCode.NETWORK_TRANSIENT,
            InviteResultCode.SERVER_TRANSIENT,
        }:
            return ClassifiedResult(MigrationItemState.RETRY, retry=True)
        return ClassifiedResult(MigrationItemState.FAILED)

from enum import StrEnum


class AccountState(StrEnum):
    """Persistent connection/authentication state.

    BUSY/WAITING_SERVER are retained for compatibility with databases produced by
    Core V1, but V1.1 derives operation status from the active Job instead of letting
    Telegram work overwrite the connection state.
    """

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    READY = "READY"
    BUSY = "BUSY"
    WAITING_SERVER = "WAITING_SERVER"
    ERROR = "ERROR"
    DISABLED = "DISABLED"


class JobState(StrEnum):
    CREATED = "CREATED"
    PREPARING = "PREPARING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_SERVER = "WAITING_SERVER"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobType(StrEnum):
    SCAN = "SCAN"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    TARGET_SCAN = "TARGET_SCAN"
    MIGRATION = "MIGRATION"
    REMOVE = "REMOVE"


class ActionType(StrEnum):
    INVITE = "INVITE"
    REMOVE = "REMOVE"


class MigrationItemState(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class TargetCoverage(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class TargetMemberState(StrEnum):
    KNOWN_ABSENT = "KNOWN_ABSENT"
    UNKNOWN_TARGET_STATE = "UNKNOWN_TARGET_STATE"
    KNOWN_PRESENT = "KNOWN_PRESENT"


class InviteResultCode(StrEnum):
    SUCCESS = "SUCCESS"
    ALREADY_MEMBER = "ALREADY_MEMBER"
    NOT_MEMBER = "NOT_MEMBER"
    PRIVACY = "PRIVACY"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    INVALID_USER = "INVALID_USER"
    PERMISSION = "PERMISSION"
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    RATE_LIMIT_INDEFINITE = "RATE_LIMIT_INDEFINITE"
    NETWORK_TRANSIENT = "NETWORK_TRANSIENT"
    SERVER_TRANSIENT = "SERVER_TRANSIENT"
    UNKNOWN = "UNKNOWN"

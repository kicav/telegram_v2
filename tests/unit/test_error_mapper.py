from tms.core.enums import InviteResultCode
from tms.telegram.error_mapper import ErrorMapper


class FloodWaitError(Exception):
    seconds = 42


class UserPrivacyRestrictedError(Exception):
    pass


class UserAlreadyParticipantError(Exception):
    pass


class PeerFloodError(Exception):
    pass


def test_error_mapping():
    mapper = ErrorMapper()
    flood = mapper.map(FloodWaitError("wait"))
    assert flood.code == InviteResultCode.RATE_LIMIT
    assert flood.wait_seconds == 42
    assert mapper.map(UserPrivacyRestrictedError()).code == InviteResultCode.PRIVACY
    assert mapper.map(UserAlreadyParticipantError()).code == InviteResultCode.ALREADY_MEMBER


def test_rate_limit_without_server_duration_pauses_instead_of_busy_loop():
    mapped = ErrorMapper().map(PeerFloodError("restricted"))
    assert mapped.code == InviteResultCode.RATE_LIMIT_INDEFINITE
    assert mapped.wait_seconds is None

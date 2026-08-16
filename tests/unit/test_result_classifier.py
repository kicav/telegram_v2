from tms.migration.result_classifier import ResultClassifier
from tms.core.errors import DomainError
from tms.core.enums import InviteResultCode,MigrationItemState

def test_policies():
    c=ResultClassifier();assert c.classify(None).state==MigrationItemState.SUCCESS
    assert c.classify(DomainError(InviteResultCode.PRIVACY,'x')).state==MigrationItemState.SKIPPED
    assert c.classify(DomainError(InviteResultCode.PERMISSION,'x')).pause_job
    r=c.classify(DomainError(InviteResultCode.RATE_LIMIT,'x',60));assert r.retry and r.wait_seconds==60

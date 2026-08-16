from tms.members.models import Member
from tms.members.filter_engine import FilterEngine
from tms.members.filter_spec import FilterSpec

def test_filter_local_dedup_and_exclusions():
    members=[Member(1,'a'),Member(1,'renamed'),Member(2,'b',bot=True),Member(3,None),Member(4,'d',deleted=True)]
    out=FilterEngine().apply(members,FilterSpec(username_required=True))
    assert [m.telegram_user_id for m in out]==[1]

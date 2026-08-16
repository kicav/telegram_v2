from time import perf_counter
from tms.members.models import Member
from tms.members.filter_engine import FilterEngine
from tms.members.filter_spec import FilterSpec

def test_filter_100k_under_reasonable_budget():
    members=[Member(i,f'u{i}') for i in range(100_000)]
    t=perf_counter();out=FilterEngine().apply(members,FilterSpec());elapsed=perf_counter()-t
    assert len(out)==100_000
    assert elapsed < 3.0

from time import perf_counter
from tms.members.models import Member
from tms.members.filter_engine import FilterEngine
from tms.members.filter_spec import FilterSpec
n=100_000
members=[Member(i,username=f'user{i}',bot=(i%101==0),deleted=(i%257==0)) for i in range(n)]
t=perf_counter();out=FilterEngine().apply(members,FilterSpec());dt=perf_counter()-t
print({'input':n,'output':len(out),'seconds':round(dt,4),'rate_per_sec':round(n/dt)})

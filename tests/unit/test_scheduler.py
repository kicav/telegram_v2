import asyncio
from tms.core.clock import FakeClock
from tms.migration.scheduler import InviteScheduler

def test_scheduler_interval_and_floodwait_server_wins():
    async def run():
        c=FakeClock();s=InviteScheduler(5,c);await s.wait_before_next();s.mark_attempt();await s.wait_before_next();assert c.now==5
        s.mark_attempt();s.apply_server_wait(120);await s.wait_before_next();assert c.now==125
    asyncio.run(run())

def test_scheduler_rejects_out_of_range():
    import pytest
    with pytest.raises(ValueError): InviteScheduler(2.9)
    with pytest.raises(ValueError): InviteScheduler(8.1)

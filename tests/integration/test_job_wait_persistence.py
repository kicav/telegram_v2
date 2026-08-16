from tms.core.enums import JobState, JobType
from tms.jobs.models import Job


def test_pause_preserves_server_wait_until_explicit_clear(store):
    job_id = store.jobs.create(Job(None, JobType.MIGRATION, JobState.RUNNING))
    wait_until = "2099-01-01T00:00:00+00:00"
    store.jobs.submit_set_state(job_id, JobState.WAITING_SERVER, wait_until).result()
    store.jobs.submit_set_state(job_id, JobState.PAUSED).result()
    assert store.jobs.get(job_id)["waiting_until"] == wait_until
    store.jobs.submit_set_state(
        job_id, JobState.RUNNING, clear_waiting=True
    ).result()
    assert store.jobs.get(job_id)["waiting_until"] is None

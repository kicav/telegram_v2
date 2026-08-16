import pytest
from tms.jobs.state_machine import validate_transition
from tms.core.enums import JobState

def test_job_transitions():
    validate_transition(JobState.READY,JobState.RUNNING)
    with pytest.raises(ValueError): validate_transition(JobState.COMPLETED,JobState.RUNNING)

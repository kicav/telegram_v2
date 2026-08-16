import pytest

from tms.accounts.models import Account
from tms.core.enums import JobState, JobType
from tms.jobs.models import Job


def test_account_delete_preserves_terminal_job_history(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+841234567", str(tmp_path / "a.session"))
    )
    job_id = store.jobs.create(
        Job(None, JobType.SCAN, JobState.COMPLETED, account_id=account_id)
    )
    store.accounts.submit_delete(account_id).result(timeout=10)
    assert store.accounts.get(account_id) is None
    row = store.jobs.get(job_id)
    assert row is not None
    assert row["account_id"] is None


def test_account_delete_rejects_nonterminal_job(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+841234568", str(tmp_path / "b.session"))
    )
    store.jobs.create(Job(None, JobType.SCAN, JobState.PAUSED, account_id=account_id))
    with pytest.raises(RuntimeError, match="non-terminal jobs"):
        store.accounts.submit_delete(account_id).result(timeout=10)
    assert store.accounts.get(account_id) is not None


def test_job_repository_detects_nonterminal_account_work(store, tmp_path):
    account_id = store.accounts.create(
        Account(None, "+841234569", str(tmp_path / "c.session"))
    )
    assert store.jobs.has_nonterminal_jobs(account_id) is False
    job_id = store.jobs.create(
        Job(None, JobType.SCAN, JobState.RUNNING, account_id=account_id)
    )
    assert store.jobs.has_nonterminal_jobs(account_id) is True
    store.jobs.submit_set_state(job_id, JobState.COMPLETED).result(timeout=10)
    assert store.jobs.has_nonterminal_jobs(account_id) is False

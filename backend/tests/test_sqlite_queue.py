from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.db.migrate import upgrade_to_head
from app.db.models import BatchRow, JobRow
from app.db.session import get_sessionmaker
from app.queue.sqlite import SQLiteJobQueue


@pytest.fixture(autouse=True)
def migrated_database() -> Iterator[None]:
    upgrade_to_head()
    yield


def _batch_id() -> str:
    with get_sessionmaker()() as session:
        row = BatchRow(name="Cola", status="draft", default_options={})
        session.add(row)
        session.commit()
        return row.id


def _queue() -> SQLiteJobQueue:
    return SQLiteJobQueue(get_sessionmaker())


def test_enqueue_and_claim_are_fifo() -> None:
    batch_id = _batch_id()
    queue = _queue()
    first = queue.enqueue("import", batch_id=batch_id, payload={"source": "first"})
    second = queue.enqueue("import", batch_id=batch_id, payload={"source": "second"})

    claimed_first = queue.claim_next("worker-1")
    claimed_second = queue.claim_next("worker-1")

    assert first.status == "queued"
    assert claimed_first is not None
    assert claimed_first.id == first.id
    assert claimed_first.status == "running"
    assert claimed_first.attempts == 1
    assert claimed_first.started_at is not None
    assert claimed_second is not None
    assert claimed_second.id == second.id
    assert queue.claim_next("worker-1") is None


def test_concurrent_claim_only_returns_a_job_once() -> None:
    batch_id = _batch_id()
    queue = _queue()
    queued = queue.enqueue("import", batch_id=batch_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(queue.claim_next, ("worker-1", "worker-2")))

    jobs = [job for job in claimed if job is not None]
    assert len(jobs) == 1
    assert jobs[0].id == queued.id


def test_fail_retries_twice_and_then_finishes_as_failed() -> None:
    batch_id = _batch_id()
    queue = _queue()
    queued = queue.enqueue("import", batch_id=batch_id)

    for expected_attempt in (1, 2):
        claimed = queue.claim_next("worker")
        assert claimed is not None
        assert claimed.attempts == expected_attempt
        queue.fail(claimed.id, f"error {expected_attempt}", retry=True)

    last = queue.claim_next("worker")
    assert last is not None
    assert last.attempts == 3
    queue.fail(last.id, "error final", retry=True)

    assert queue.claim_next("worker") is None
    with get_sessionmaker()() as session:
        row = session.get(JobRow, queued.id)
        assert row is not None
        assert row.status == "failed"
        assert row.error == "error final"
        assert row.finished_at is not None


def test_complete_requires_running_job() -> None:
    batch_id = _batch_id()
    queue = _queue()
    queued = queue.enqueue("import", batch_id=batch_id)

    with pytest.raises(ValueError, match="ejecución"):
        queue.complete(queued.id)
    claimed = queue.claim_next("worker")
    assert claimed is not None
    queue.complete(claimed.id)

    with get_sessionmaker()() as session:
        row = session.get(JobRow, claimed.id)
        assert row is not None
        assert row.status == "done"
        assert row.finished_at is not None


def test_cancel_batch_leaves_running_jobs_and_recover_stale_requeues_them() -> None:
    batch_id = _batch_id()
    queue = _queue()
    running = queue.enqueue("import", batch_id=batch_id)
    queued = queue.enqueue("import", batch_id=batch_id)
    claimed = queue.claim_next("worker")
    assert claimed is not None
    assert claimed.id == running.id

    assert queue.cancel_batch(batch_id) == 1
    assert queue.recover_stale() == 1

    recovered = queue.claim_next("other-worker")
    assert recovered is not None
    assert recovered.id == running.id
    assert recovered.attempts == 2
    assert queue.claim_next("other-worker") is None

    with get_sessionmaker()() as session:
        cancelled = session.get(JobRow, queued.id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert cancelled.finished_at is not None


def test_enqueue_requires_an_owner_and_missing_job_raises() -> None:
    queue = _queue()
    with pytest.raises(ValueError, match="imagen o a un lote"):
        queue.enqueue("import")
    with pytest.raises(KeyError, match="Trabajo no encontrado"):
        queue.complete("missing")

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from research_agent.models import AuditEvent, ResearchRun, RunStatus, Topic
from research_agent.services import recover_stale_runs


def test_stale_running_job_returns_to_queue_after_restart(session) -> None:  # type: ignore[no-untyped-def]
    topic = Topic(title="Restart test", question="Can this job recover safely?", keywords=[])
    session.add(topic)
    session.flush()
    run = ResearchRun(
        topic_id=topic.id,
        status=RunStatus.RUNNING,
        started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    session.add(run)
    session.commit()

    recovered_count = recover_stale_runs(session, stale_after_minutes=15)

    assert recovered_count == 1
    assert run.status == RunStatus.QUEUED
    assert run.progress_stage == "recovered_after_restart"
    assert session.scalar(select(AuditEvent).where(AuditEvent.run_id == run.id)) is not None

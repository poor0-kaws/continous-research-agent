import time
from datetime import UTC, datetime

from sqlalchemy import select

from research_agent.config import get_settings
from research_agent.db import SessionLocal, create_schema
from research_agent.discovery import DiscoveryClient
from research_agent.embedding import LocalEmbedder
from research_agent.groq_client import GroqClient
from research_agent.models import ResearchRun, RunStatus
from research_agent.quota import QuotaExhausted, QuotaManager
from research_agent.security import GuardedFetcher
from research_agent.services import (
    ResearchPipeline,
    add_audit,
    enqueue_due_topics,
    recover_stale_runs,
)


def build_pipeline() -> ResearchPipeline:
    settings = get_settings()
    quota = QuotaManager(settings)
    return ResearchPipeline(
        groq=GroqClient(settings, quota),
        fetcher=GuardedFetcher(max_bytes=settings.max_source_bytes),
        embedder=LocalEmbedder(),
        discovery=DiscoveryClient(max_bytes=settings.max_source_bytes),
    )


def process_one_run(pipeline: ResearchPipeline) -> bool:
    with SessionLocal() as session:
        statement = (
            select(ResearchRun)
            .where(ResearchRun.status == RunStatus.QUEUED)
            .order_by(ResearchRun.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        run = session.scalar(statement)
        if run is None:
            return False

        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        run.attempt_count += 1
        session.commit()

        try:
            if run.kind == "verify":
                pipeline.verify_draft(session, run)
            else:
                pipeline.create_research_draft(session, run)
            run.status = RunStatus.COMPLETED
            run.progress_stage = "completed"
        except QuotaExhausted as error:
            run.status = RunStatus.PAUSED_QUOTA
            run.progress_stage = "quota_exhausted"
            run.error_message = str(error)
            add_audit(
                session,
                "run_paused_for_quota",
                "The free-tier limit paused this run; no paid fallback was used",
                topic_id=run.topic_id,
                run_id=run.id,
                details={"reason": str(error)},
            )
        except Exception as error:
            can_retry = run.attempt_count < run.max_attempts
            run.status = RunStatus.QUEUED if can_retry else RunStatus.FAILED
            run.progress_stage = "retry_queued" if can_retry else "failed"
            run.error_message = str(error)[:2_000]
            add_audit(
                session,
                "run_retry_queued" if can_retry else "run_failed",
                "A failed run was queued for a safe retry"
                if can_retry
                else "A research worker run failed safely",
                topic_id=run.topic_id,
                run_id=run.id,
                details={"error": str(error)[:500]},
            )

        run.finished_at = None if run.status == RunStatus.QUEUED else datetime.now(UTC)
        if run.status == RunStatus.QUEUED:
            run.started_at = None
        session.commit()
        return True


def main() -> None:
    create_schema()
    settings = get_settings()
    pipeline = build_pipeline()
    while True:
        with SessionLocal() as session:
            recover_stale_runs(session)
            enqueue_due_topics(session)
        worked = process_one_run(pipeline)
        if not worked:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()

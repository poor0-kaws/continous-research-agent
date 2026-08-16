from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from research_agent.db import Base


def new_id() -> str:
    return str(uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class KnowledgeStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PARTIALLY_CONFIRMED = "partially_confirmed"
    CONTESTED = "contested"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED_QUOTA = "paused_quota"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    question: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled_source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    rss_feed_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    schedule_hour: Mapped[int] = mapped_column(Integer, default=3)
    timezone: Mapped[str] = mapped_column(String(80), default="America/New_York")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourceCatalogEntry(TimestampMixin, Base):
    __tablename__ = "source_catalog_entries"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    publisher: Mapped[str] = mapped_column(String(200))
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    allowed_paths: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["/"])
    category: Mapped[str] = mapped_column(String(80), index=True)
    topic_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_role: Mapped[str] = mapped_column(String(40))
    access_mode: Mapped[str] = mapped_column(String(40))
    approval_reason: Mapped[str] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)


class ResearchRun(TimestampMixin, Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_drafts.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30), default="research")
    trigger: Mapped[str] = mapped_column(String(30), default="manual")
    status: Mapped[str] = mapped_column(String(30), default=RunStatus.QUEUED)
    progress_stage: Mapped[str] = mapped_column(String(80), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    model_requests: Mapped[int] = mapped_column(Integer, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)


class ResearchDraft(TimestampMixin, Base):
    __tablename__ = "research_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    report_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=KnowledgeStatus.PENDING)
    searched_domains: Mapped[list[str]] = mapped_column(JSON, default=list)
    cited_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_name: Mapped[str] = mapped_column(String(80), default="groq/compound")
    raw_response_hash: Mapped[str] = mapped_column(String(64))


class SearchLead(TimestampMixin, Base):
    __tablename__ = "search_leads"
    __table_args__ = (UniqueConstraint("draft_id", "url", name="uq_draft_lead_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("research_drafts.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(200))
    access_mode: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="candidate")


class CandidateClaim(TimestampMixin, Base):
    __tablename__ = "candidate_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("research_drafts.id", ondelete="CASCADE"), index=True
    )
    statement: Mapped[str] = mapped_column(Text)
    citation_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default=KnowledgeStatus.PENDING)
    importance: Mapped[str] = mapped_column(String(20), default="normal")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(384).with_variant(JSON(), "sqlite"), nullable=True
    )


class CandidateConnection(TimestampMixin, Base):
    __tablename__ = "candidate_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("research_drafts.id", ondelete="CASCADE"), index=True
    )
    source_label: Mapped[str] = mapped_column(String(250))
    target_label: Mapped[str] = mapped_column(String(250))
    relationship: Mapped[str] = mapped_column(String(80))
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=KnowledgeStatus.PENDING)


class CandidateInsight(TimestampMixin, Base):
    __tablename__ = "candidate_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("research_drafts.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    explanation: Mapped[str] = mapped_column(Text)
    supporting_claim_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    conflicting_claim_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String(20), default="low")
    verification_status: Mapped[str] = mapped_column(String(30), default=KnowledgeStatus.PENDING)
    review_status: Mapped[str] = mapped_column(String(20), default="draft")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("canonical_url", "content_hash", name="uq_document_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_catalog_entries.id"), index=True)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(200))
    content_hash: Mapped[str] = mapped_column(String(64))
    sanitized_text: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EvidenceExcerpt(TimestampMixin, Base):
    __tablename__ = "evidence_excerpts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_claims.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    excerpt: Mapped[str] = mapped_column(Text)
    locator: Mapped[str] = mapped_column(String(200), default="body")
    stance: Mapped[str] = mapped_column(String(30), default="supports")


class VerificationResult(TimestampMixin, Base):
    __tablename__ = "verification_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_claims.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30))
    rationale: Mapped[str] = mapped_column(Text)
    supporting_source_count: Mapped[int] = mapped_column(Integer, default=0)
    conflicting_source_count: Mapped[int] = mapped_column(Integer, default=0)
    source_independence: Mapped[float] = mapped_column(Float, default=0.0)


class Concept(TimestampMixin, Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("topic_id", "normalized_name", name="uq_topic_concept"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(250))
    normalized_name: Mapped[str] = mapped_column(String(250))
    kind: Mapped[str] = mapped_column(String(80), default="concept")
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(384).with_variant(JSON(), "sqlite"), nullable=True
    )


class GraphEdge(TimestampMixin, Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint("topic_id", "source_id", "target_id", "relationship", name="uq_edge"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    relationship: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default=KnowledgeStatus.CONFIRMED)


class QuarantineRecord(TimestampMixin, Base):
    __tablename__ = "quarantine_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    detector: Mapped[str] = mapped_column(String(80))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class QuotaLedger(TimestampMixin, Base):
    __tablename__ = "quota_ledger"
    __table_args__ = (UniqueConstraint("provider", "model", "day", name="uq_quota_day"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    day: Mapped[str] = mapped_column(String(10))
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

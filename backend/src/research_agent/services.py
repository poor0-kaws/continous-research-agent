import hashlib
from datetime import UTC, datetime, timedelta, tzinfo
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.catalog import (
    choose_relevant_sources,
    enabled_sources_for_topic,
    group_domain_batches,
)
from research_agent.discovery import DiscoveryClient
from research_agent.embedding import LocalEmbedder
from research_agent.groq_client import GroqClient
from research_agent.models import (
    AuditEvent,
    CandidateClaim,
    CandidateConnection,
    CandidateInsight,
    Concept,
    Document,
    EvidenceExcerpt,
    GraphEdge,
    KnowledgeStatus,
    QuarantineRecord,
    ResearchDraft,
    ResearchRun,
    SearchLead,
    Topic,
    VerificationResult,
    now_utc,
)
from research_agent.security import (
    GuardedFetcher,
    SourceSafetyError,
    contains_prompt_injection,
    source_for_url,
)


def add_audit(
    session: Session,
    event_type: str,
    message: str,
    *,
    topic_id: str | None = None,
    run_id: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            event_type=event_type,
            message=message,
            topic_id=topic_id,
            run_id=run_id,
            details=details or {},
        )
    )


def confirmed_graph_context(session: Session, topic_id: str) -> list[str]:
    statement = (
        select(CandidateClaim.statement)
        .where(
            CandidateClaim.topic_id == topic_id,
            CandidateClaim.status == KnowledgeStatus.CONFIRMED,
        )
        .order_by(CandidateClaim.updated_at.desc())
        .limit(30)
    )
    return list(session.scalars(statement))


class ResearchPipeline:
    def __init__(
        self,
        groq: GroqClient,
        fetcher: GuardedFetcher,
        embedder: LocalEmbedder,
        discovery: DiscoveryClient | None = None,
    ) -> None:
        self.groq = groq
        self.fetcher = fetcher
        self.embedder = embedder
        self.discovery = discovery

    def create_research_draft(self, session: Session, run: ResearchRun) -> ResearchDraft:
        topic = session.get(Topic, run.topic_id)
        if topic is None:
            raise ValueError("Research topic no longer exists")

        sources = enabled_sources_for_topic(session, topic)
        relevant_sources = choose_relevant_sources(topic, sources)
        domain_batches = group_domain_batches(relevant_sources)
        if not domain_batches:
            raise ValueError("No approved sources are enabled for this topic")

        discovery_leads = []
        if self.discovery is not None:
            discovery_leads = self.discovery.discover(topic, relevant_sources)

        run.progress_stage = "browser_research"
        session.commit()
        result = self.groq.research(
            session,
            topic.question,
            topic.keywords,
            confirmed_graph_context(session, topic.id),
            domain_batches,
        )
        run.model_requests += len(domain_batches[:6])

        if contains_prompt_injection(result.report_text):
            session.add(
                QuarantineRecord(
                    topic_id=topic.id,
                    url="groq://research-draft",
                    reason="Browser research report repeated likely prompt-injection instructions",
                    detector="local-patterns",
                    content_hash=hashlib.sha256(result.report_text.encode()).hexdigest(),
                )
            )
            raise SourceSafetyError("Browser research draft failed the injection scan")

        valid_results = []
        for result_item in result.search_results:
            result_url = str(result_item.url)
            try:
                source = source_for_url(result_url, relevant_sources)
            except SourceSafetyError:
                add_audit(
                    session,
                    "search_result_rejected",
                    "Groq returned a URL outside the approved source batch",
                    topic_id=topic.id,
                    run_id=run.id,
                    details={"url": result_url},
                )
                continue
            valid_results.append((result_item, source))

        valid_urls = {str(item.url) for item, _ in valid_results}
        draft = ResearchDraft(
            topic_id=topic.id,
            run_id=run.id,
            report_text=result.report_text,
            searched_domains=result.searched_domains,
            cited_urls=sorted(valid_urls),
            raw_response_hash=hashlib.sha256(result.report_text.encode()).hexdigest(),
        )
        session.add(draft)
        session.flush()
        run.draft_id = draft.id

        for item, source in valid_results:
            self._save_lead(
                session,
                topic_id=topic.id,
                draft_id=draft.id,
                title=item.title[:1_000],
                url=str(item.url),
                publisher=source.publisher,
                access_mode=source.access_mode,
            )

        for lead in discovery_leads:
            self._save_lead(
                session,
                topic_id=topic.id,
                draft_id=draft.id,
                title=lead.title,
                url=lead.url,
                publisher=lead.publisher,
                access_mode=lead.access_mode,
                status="discovery_only",
            )

        run.progress_stage = "draft_parsing"
        session.commit()
        parsed = self.groq.parse_draft(session, result.report_text)
        run.model_requests += 1

        claims: list[CandidateClaim] = []
        for parsed_claim in parsed.claims:
            citations = [url for url in parsed_claim.citation_urls if url in valid_urls]
            status = KnowledgeStatus.PENDING if citations else KnowledgeStatus.REJECTED
            claim = CandidateClaim(
                topic_id=topic.id,
                draft_id=draft.id,
                statement=parsed_claim.statement,
                citation_urls=citations,
                status=status,
                importance=parsed_claim.importance,
            )
            session.add(claim)
            claims.append(claim)

        for connection in parsed.connections:
            session.add(
                CandidateConnection(
                    topic_id=topic.id,
                    draft_id=draft.id,
                    source_label=connection.source_label,
                    target_label=connection.target_label,
                    relationship=connection.relationship,
                    rationale=connection.rationale,
                )
            )

        session.flush()
        for insight in parsed.insights:
            support_ids = [
                claims[number - 1].id
                for number in insight.supporting_claim_numbers
                if 0 < number <= len(claims)
            ]
            session.add(
                CandidateInsight(
                    topic_id=topic.id,
                    draft_id=draft.id,
                    title=insight.title,
                    explanation=insight.explanation,
                    supporting_claim_ids=support_ids,
                )
            )

        add_audit(
            session,
            "research_draft_created",
            "Browser research was stored as an untrusted draft",
            topic_id=topic.id,
            run_id=run.id,
            details={"draft_id": draft.id, "candidate_claims": len(claims)},
        )
        run.documents_processed = len(valid_results)
        return draft

    def _save_lead(
        self,
        session: Session,
        *,
        topic_id: str,
        draft_id: str,
        title: str,
        url: str,
        publisher: str,
        access_mode: str,
        status: str = "candidate",
    ) -> None:
        lead = session.scalar(
            select(SearchLead).where(SearchLead.draft_id == draft_id, SearchLead.url == url)
        )
        if lead is None:
            session.add(
                SearchLead(
                    topic_id=topic_id,
                    draft_id=draft_id,
                    title=title,
                    url=url,
                    publisher=publisher,
                    access_mode=access_mode,
                    status=status,
                )
            )
            return
        lead.draft_id = draft_id
        lead.title = title
        lead.publisher = publisher
        lead.access_mode = access_mode
        lead.status = status

    def verify_draft(self, session: Session, run: ResearchRun) -> None:
        if not run.draft_id:
            raise ValueError("Verification run has no research draft")
        draft = session.get(ResearchDraft, run.draft_id)
        if draft is None:
            raise ValueError("Research draft no longer exists")
        topic = session.get(Topic, draft.topic_id)
        if topic is None:
            raise ValueError("Research topic no longer exists")

        sources = enabled_sources_for_topic(session, topic)
        claims = list(
            session.scalars(
                select(CandidateClaim).where(
                    CandidateClaim.draft_id == draft.id,
                    CandidateClaim.status == KnowledgeStatus.PENDING,
                )
            )
        )
        run.progress_stage = "verification"
        session.commit()

        for claim in claims:
            self._verify_claim(session, run, claim, sources)

        self._publish_connections_and_insights(session, draft)
        statuses = {claim.status for claim in claims}
        if statuses == {KnowledgeStatus.CONFIRMED}:
            draft.status = KnowledgeStatus.CONFIRMED
        elif KnowledgeStatus.CONTESTED in statuses:
            draft.status = KnowledgeStatus.CONTESTED
        elif KnowledgeStatus.CONFIRMED in statuses:
            draft.status = KnowledgeStatus.PARTIALLY_CONFIRMED
        else:
            draft.status = KnowledgeStatus.UNVERIFIED

        add_audit(
            session,
            "research_draft_verified",
            "The confirmation pipeline finished checking browser conclusions",
            topic_id=topic.id,
            run_id=run.id,
            details={"draft_id": draft.id, "status": draft.status},
        )

    def _verify_claim(
        self,
        session: Session,
        run: ResearchRun,
        claim: CandidateClaim,
        sources: list,
    ) -> None:
        evidence_payload: list[dict[str, str]] = []
        documents_by_url: dict[str, Document] = {}

        for url in claim.citation_urls:
            try:
                safe_document = self.fetcher.fetch(url, sources)
                if self.groq.scan_prompt_injection(session, safe_document.text):
                    raise SourceSafetyError("Prompt Guard classified source text as an injection")
            except (SourceSafetyError, httpx.HTTPError, OSError, ValueError) as error:
                session.add(
                    QuarantineRecord(
                        topic_id=claim.topic_id,
                        url=url,
                        reason=str(error),
                        detector="guarded-fetcher",
                    )
                )
                add_audit(
                    session,
                    "source_rejected",
                    "A cited source failed an independent safety or access check",
                    topic_id=claim.topic_id,
                    run_id=run.id,
                    details={"url": url, "reason": str(error)[:500]},
                )
                continue

            document = session.scalar(
                select(Document).where(
                    Document.canonical_url == safe_document.url,
                    Document.content_hash == safe_document.content_hash,
                )
            )
            if document is None:
                document = Document(
                    source_id=safe_document.source.id,
                    canonical_url=safe_document.url,
                    title=safe_document.title,
                    publisher=safe_document.source.publisher,
                    content_hash=safe_document.content_hash,
                    sanitized_text=safe_document.text[:100_000],
                )
                session.add(document)
                session.flush()
            documents_by_url[safe_document.url] = document
            evidence_payload.append({"url": safe_document.url, "text": safe_document.text[:18_000]})
            add_audit(
                session,
                "source_fetched",
                "An approved source was fetched through the guarded evidence path",
                topic_id=claim.topic_id,
                run_id=run.id,
                details={"url": safe_document.url, "content_hash": safe_document.content_hash},
            )

        if not evidence_payload:
            claim.status = KnowledgeStatus.UNVERIFIED
            session.add(
                VerificationResult(
                    claim_id=claim.id,
                    status=KnowledgeStatus.UNVERIFIED,
                    rationale="No approved, freely accessible evidence could be fetched",
                )
            )
            add_audit(
                session,
                "claim_verification_decided",
                "A candidate claim could not be confirmed from accessible evidence",
                topic_id=claim.topic_id,
                run_id=run.id,
                details={"claim_id": claim.id, "status": KnowledgeStatus.UNVERIFIED},
            )
            return

        verification = self.groq.verify_claim(session, claim.statement, evidence_payload)
        run.model_requests += 1
        hostnames = {urlsplit(item["url"]).hostname for item in evidence_payload}
        status = KnowledgeStatus(verification.status)
        if (
            claim.importance == "important"
            and status == KnowledgeStatus.CONFIRMED
            and len(hostnames) < 2
        ):
            status = KnowledgeStatus.PARTIALLY_CONFIRMED

        supporting_count = 0
        conflicting_count = 0
        for excerpt in verification.excerpts:
            document = documents_by_url.get(excerpt.url)
            if document is None or excerpt.excerpt not in document.sanitized_text:
                continue
            if excerpt.stance == "supports":
                supporting_count += 1
            else:
                conflicting_count += 1
            session.add(
                EvidenceExcerpt(
                    claim_id=claim.id,
                    document_id=document.id,
                    excerpt=excerpt.excerpt[:2_000],
                    locator=excerpt.locator[:200],
                    stance=excerpt.stance,
                )
            )

        if status == KnowledgeStatus.CONFIRMED and supporting_count == 0:
            status = KnowledgeStatus.UNVERIFIED
        if supporting_count and conflicting_count:
            status = KnowledgeStatus.CONTESTED

        claim.status = status
        if status == KnowledgeStatus.CONFIRMED:
            claim.published_at = now_utc()
            claim.embedding = self.embedder.embed([claim.statement])[0]

        session.add(
            VerificationResult(
                claim_id=claim.id,
                status=status,
                rationale=verification.rationale,
                supporting_source_count=supporting_count,
                conflicting_source_count=conflicting_count,
                source_independence=min(1.0, len(hostnames) / 3),
            )
        )
        add_audit(
            session,
            "claim_verification_decided",
            "A candidate claim received an independent confirmation result",
            topic_id=claim.topic_id,
            run_id=run.id,
            details={
                "claim_id": claim.id,
                "status": status,
                "supporting_excerpts": supporting_count,
                "conflicting_excerpts": conflicting_count,
            },
        )
        session.commit()

    def _publish_connections_and_insights(self, session: Session, draft: ResearchDraft) -> None:
        confirmed_claims = list(
            session.scalars(
                select(CandidateClaim).where(
                    CandidateClaim.draft_id == draft.id,
                    CandidateClaim.status == KnowledgeStatus.CONFIRMED,
                )
            )
        )
        if len(confirmed_claims) < 2:
            return

        connections = list(
            session.scalars(
                select(CandidateConnection).where(CandidateConnection.draft_id == draft.id)
            )
        )
        for connection in connections:
            source = self._get_or_create_concept(session, draft.topic_id, connection.source_label)
            target = self._get_or_create_concept(session, draft.topic_id, connection.target_label)
            session.flush()
            edge = session.scalar(
                select(GraphEdge).where(
                    GraphEdge.topic_id == draft.topic_id,
                    GraphEdge.source_id == source.id,
                    GraphEdge.target_id == target.id,
                    GraphEdge.relationship == connection.relationship,
                )
            )
            if edge is None:
                session.add(
                    GraphEdge(
                        topic_id=draft.topic_id,
                        source_id=source.id,
                        target_id=target.id,
                        relationship=connection.relationship,
                    )
                )
            connection.status = KnowledgeStatus.CONFIRMED

        insights = list(
            session.scalars(select(CandidateInsight).where(CandidateInsight.draft_id == draft.id))
        )
        confirmed_ids = {claim.id for claim in confirmed_claims}
        for insight in insights:
            supported = confirmed_ids.intersection(insight.supporting_claim_ids)
            if len(supported) < 3:
                insight.verification_status = KnowledgeStatus.UNVERIFIED
                continue
            insight.verification_status = KnowledgeStatus.PARTIALLY_CONFIRMED
            insight.confidence = "medium" if len(supported) < 5 else "high"

    def _get_or_create_concept(self, session: Session, topic_id: str, name: str) -> Concept:
        normalized = " ".join(name.lower().split())
        concept = session.scalar(
            select(Concept).where(
                Concept.topic_id == topic_id,
                Concept.normalized_name == normalized,
            )
        )
        if concept:
            return concept
        return Concept(
            topic_id=topic_id,
            name=name[:250],
            normalized_name=normalized[:250],
            embedding=self.embedder.embed([name])[0],
        )


def next_daily_run(hour: int, timezone_name: str) -> datetime:
    now = datetime.now(UTC)
    local_timezone: tzinfo
    try:
        local_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        local_timezone = UTC
    local_now = now.astimezone(local_timezone)
    local_candidate = local_now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if local_candidate <= local_now:
        local_candidate += timedelta(days=1)
    return local_candidate.astimezone(UTC)


def recover_stale_runs(session: Session, stale_after_minutes: int = 15) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=stale_after_minutes)
    stale_runs = list(
        session.scalars(
            select(ResearchRun).where(
                ResearchRun.status == "running",
                ResearchRun.started_at.is_not(None),
                ResearchRun.started_at < cutoff,
            )
        )
    )
    for run in stale_runs:
        run.status = "queued"
        run.progress_stage = "recovered_after_restart"
        run.started_at = None
        add_audit(
            session,
            "run_recovered",
            "A run interrupted by a restart was returned to the queue",
            topic_id=run.topic_id,
            run_id=run.id,
        )
    session.commit()
    return len(stale_runs)


def enqueue_due_topics(session: Session) -> int:
    now = datetime.now(UTC)
    topics = list(
        session.scalars(
            select(Topic).where(
                Topic.is_active.is_(True),
                Topic.next_run_at.is_not(None),
                Topic.next_run_at <= now,
            )
        )
    )
    for topic in topics:
        session.add(ResearchRun(topic_id=topic.id, trigger="scheduled", kind="research"))
        topic.next_run_at = next_daily_run(topic.schedule_hour, topic.timezone)
    session.commit()
    return len(topics)

from datetime import UTC, datetime

from sqlalchemy import select

from research_agent.groq_client import BrowserResearchResult
from research_agent.models import (
    CandidateClaim,
    Concept,
    Document,
    EvidenceExcerpt,
    KnowledgeStatus,
    ResearchDraft,
    ResearchRun,
    SourceCatalogEntry,
    Topic,
)
from research_agent.schemas import (
    ClaimVerification,
    GroqSearchResult,
    ParsedClaim,
    ParsedDraft,
    VerifiedExcerpt,
)
from research_agent.security import SafeDocument
from research_agent.services import ResearchPipeline


def approved_source(access_mode: str = "full_text") -> SourceCatalogEntry:
    return SourceCatalogEntry(
        id="approved-news",
        publisher="Approved News",
        hostname="approved.example",
        allowed_paths=["/article/"],
        category="news",
        topic_tags=["science"],
        evidence_role="secondary" if access_mode == "full_text" else "discovery_only",
        access_mode=access_mode,
        approval_reason="A reviewed source used by this isolated test",
        reviewed_at=datetime.now(UTC),
    )


class FakeEmbedder:
    def embed(self, texts):  # type: ignore[no-untyped-def]
        return [[0.1] * 384 for _ in texts]


class DraftGroq:
    def research(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return BrowserResearchResult(
            report_text="Approved research report with citations.",
            search_results=[
                GroqSearchResult(
                    title="Approved",
                    url="https://approved.example/article/1",
                    content="safe",
                    score=0.9,
                ),
                GroqSearchResult(
                    title="Injected bad source",
                    url="https://bad.example/article/2",
                    content="bad",
                    score=0.99,
                ),
            ],
            searched_domains=["approved.example"],
        )

    def parse_draft(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return ParsedDraft(
            claims=[
                ParsedClaim(
                    statement="The approved source reports a change.",
                    citation_urls=["https://approved.example/article/1"],
                    importance="normal",
                )
            ],
            connections=[],
            insights=[],
        )


class VerifyGroq:
    def scan_prompt_injection(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return False

    def verify_claim(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return ClaimVerification(
            status="confirmed",
            rationale="The evidence says the same thing.",
            excerpts=[
                VerifiedExcerpt(
                    url="https://approved.example/article/1",
                    excerpt="The measured value increased by ten percent.",
                    locator="paragraph 2",
                    stance="supports",
                )
            ],
        )


class FabricatedExcerptGroq(VerifyGroq):
    def verify_claim(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return ClaimVerification(
            status="confirmed",
            rationale="The model claimed support, but invented its quotation.",
            excerpts=[
                VerifiedExcerpt(
                    url="https://approved.example/article/1",
                    excerpt="This sentence does not exist in the fetched page.",
                    locator="paragraph 99",
                    stance="supports",
                )
            ],
        )


class ConflictingGroq(VerifyGroq):
    def verify_claim(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return ClaimVerification(
            status="confirmed",
            rationale="The approved sources disagree.",
            excerpts=[
                VerifiedExcerpt(
                    url="https://approved.example/article/1",
                    excerpt="The measured value increased by ten percent.",
                    locator="paragraph 2",
                    stance="supports",
                ),
                VerifiedExcerpt(
                    url="https://second.example/article/2",
                    excerpt="The measured value did not increase.",
                    locator="paragraph 4",
                    stance="conflicts",
                ),
            ],
        )


class FakeFetcher:
    def __init__(self, source: SourceCatalogEntry):
        self.source = source

    def fetch(self, url, sources):  # type: ignore[no-untyped-def]
        return SafeDocument(
            url=url,
            title="Approved evidence",
            text="The measured value increased by ten percent. This is enough readable evidence.",
            content_hash="abc123",
            source=self.source,
        )


class MultiFetcher:
    def __init__(self, sources: list[SourceCatalogEntry]):
        self.sources = {source.hostname: source for source in sources}

    def fetch(self, url, sources):  # type: ignore[no-untyped-def]
        hostname = url.split("/")[2]
        source = self.sources[hostname]
        text = "The measured value increased by ten percent."
        if hostname == "second.example":
            text = "The measured value did not increase."
        return SafeDocument(
            url=url,
            title="Approved evidence",
            text=text,
            content_hash=f"hash-{hostname}",
            source=source,
        )


def test_browser_result_outside_catalog_never_becomes_a_claim(session) -> None:  # type: ignore[no-untyped-def]
    source = approved_source()
    topic = Topic(
        title="Science",
        question="What changed in this field recently?",
        keywords=["science"],
    )
    session.add_all([source, topic])
    session.flush()
    run = ResearchRun(topic_id=topic.id)
    session.add(run)
    session.commit()

    pipeline = ResearchPipeline(DraftGroq(), FakeFetcher(source), FakeEmbedder())  # type: ignore[arg-type]
    draft = pipeline.create_research_draft(session, run)
    session.commit()

    assert draft.status == KnowledgeStatus.PENDING
    assert draft.cited_urls == ["https://approved.example/article/1"]
    claims = list(session.scalars(select(CandidateClaim)))
    assert len(claims) == 1
    assert claims[0].published_at is None
    assert session.scalar(select(Concept)) is None


def test_confirmation_requires_an_exact_excerpt_before_publication(session) -> None:  # type: ignore[no-untyped-def]
    source = approved_source()
    topic = Topic(title="Science", question="What evidence supports this change?", keywords=[])
    session.add_all([source, topic])
    session.flush()
    draft = ResearchDraft(
        topic_id=topic.id,
        report_text="draft",
        searched_domains=[source.hostname],
        cited_urls=["https://approved.example/article/1"],
        raw_response_hash="hash",
    )
    session.add(draft)
    session.flush()
    claim = CandidateClaim(
        topic_id=topic.id,
        draft_id=draft.id,
        statement="The measured value increased.",
        citation_urls=["https://approved.example/article/1"],
    )
    session.add(claim)
    session.flush()
    run = ResearchRun(topic_id=topic.id, draft_id=draft.id, kind="verify")
    session.add(run)
    session.commit()

    pipeline = ResearchPipeline(VerifyGroq(), FakeFetcher(source), FakeEmbedder())  # type: ignore[arg-type]
    pipeline.verify_draft(session, run)
    session.commit()

    session.refresh(claim)
    assert claim.status == KnowledgeStatus.CONFIRMED
    assert claim.published_at is not None
    assert session.scalar(select(Document)) is not None
    assert session.scalar(select(EvidenceExcerpt)) is not None


def test_fabricated_excerpt_cannot_publish_a_claim(session) -> None:  # type: ignore[no-untyped-def]
    source = approved_source()
    topic = Topic(title="Science", question="What changed?", keywords=[])
    session.add_all([source, topic])
    session.flush()
    draft = ResearchDraft(
        topic_id=topic.id,
        report_text="draft",
        searched_domains=[source.hostname],
        cited_urls=["https://approved.example/article/1"],
        raw_response_hash="hash",
    )
    session.add(draft)
    session.flush()
    claim = CandidateClaim(
        topic_id=topic.id,
        draft_id=draft.id,
        statement="The value increased.",
        citation_urls=draft.cited_urls,
    )
    session.add(claim)
    session.flush()
    run = ResearchRun(topic_id=topic.id, draft_id=draft.id, kind="verify")
    session.add(run)
    session.commit()

    pipeline = ResearchPipeline(
        FabricatedExcerptGroq(),
        FakeFetcher(source),
        FakeEmbedder(),  # type: ignore[arg-type]
    )
    pipeline.verify_draft(session, run)
    session.commit()

    assert claim.status == KnowledgeStatus.UNVERIFIED
    assert claim.published_at is None
    assert session.scalar(select(EvidenceExcerpt)) is None


def test_conflicting_approved_sources_create_a_contested_claim(session) -> None:  # type: ignore[no-untyped-def]
    first = approved_source()
    second = approved_source()
    second.id = "second-news"
    second.hostname = "second.example"
    topic = Topic(title="Science", question="Did the value change?", keywords=[])
    session.add_all([first, second, topic])
    session.flush()
    urls = [
        "https://approved.example/article/1",
        "https://second.example/article/2",
    ]
    draft = ResearchDraft(
        topic_id=topic.id,
        report_text="draft",
        searched_domains=[first.hostname, second.hostname],
        cited_urls=urls,
        raw_response_hash="hash",
    )
    session.add(draft)
    session.flush()
    claim = CandidateClaim(
        topic_id=topic.id,
        draft_id=draft.id,
        statement="The value increased.",
        citation_urls=urls,
    )
    session.add(claim)
    session.flush()
    run = ResearchRun(topic_id=topic.id, draft_id=draft.id, kind="verify")
    session.add(run)
    session.commit()

    pipeline = ResearchPipeline(
        ConflictingGroq(),
        MultiFetcher([first, second]),
        FakeEmbedder(),  # type: ignore[arg-type]
    )
    pipeline.verify_draft(session, run)
    session.commit()

    assert claim.status == KnowledgeStatus.CONTESTED
    assert claim.published_at is None
    assert len(list(session.scalars(select(EvidenceExcerpt)))) == 2

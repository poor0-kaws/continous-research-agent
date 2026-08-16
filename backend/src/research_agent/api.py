from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.db import get_session
from research_agent.models import (
    CandidateClaim,
    CandidateConnection,
    CandidateInsight,
    Concept,
    GraphEdge,
    KnowledgeStatus,
    ResearchDraft,
    ResearchRun,
    RunStatus,
    SearchLead,
    SourceCatalogEntry,
    Topic,
    VerificationResult,
)
from research_agent.schemas import (
    CandidateClaimRead,
    CandidateConnectionRead,
    CandidateInsightPatch,
    CandidateInsightRead,
    GraphEdgeRead,
    GraphNode,
    GraphResponse,
    ResearchDraftDetail,
    ResearchDraftSummary,
    ResearchRunRead,
    SearchLeadRead,
    SourceCatalogCreate,
    SourceCatalogPatch,
    SourceCatalogRead,
    TopicCreate,
    TopicRead,
    TopicUpdate,
    VerificationResultRead,
)
from research_agent.services import add_audit, next_daily_run

router = APIRouter(prefix="/api")


def get_or_404(session: Session, model: type, item_id: str):  # type: ignore[no-untyped-def]
    item = session.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item was not found")
    return item


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/topics", response_model=TopicRead, status_code=status.HTTP_201_CREATED)
def create_topic(payload: TopicCreate, session: Session = Depends(get_session)) -> Topic:
    topic = Topic(
        **payload.model_dump(),
        next_run_at=next_daily_run(payload.schedule_hour, payload.timezone),
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


@router.get("/topics", response_model=list[TopicRead])
def list_topics(session: Session = Depends(get_session)) -> list[Topic]:
    return list(session.scalars(select(Topic).order_by(Topic.created_at.desc())))


@router.patch("/topics/{topic_id}", response_model=TopicRead)
def update_topic(
    topic_id: str, payload: TopicUpdate, session: Session = Depends(get_session)
) -> Topic:
    topic = get_or_404(session, Topic, topic_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(topic, key, value)
    if payload.schedule_hour is not None or payload.timezone is not None:
        topic.next_run_at = next_daily_run(topic.schedule_hour, topic.timezone)
    session.commit()
    session.refresh(topic)
    return topic


@router.post("/topics/{topic_id}/runs", response_model=ResearchRunRead, status_code=202)
def start_research_run(topic_id: str, session: Session = Depends(get_session)) -> ResearchRun:
    get_or_404(session, Topic, topic_id)
    active = session.scalar(
        select(ResearchRun).where(
            ResearchRun.topic_id == topic_id,
            ResearchRun.kind == "research",
            ResearchRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    )
    if active:
        return active

    run = ResearchRun(topic_id=topic_id, trigger="manual", kind="research")
    session.add(run)
    add_audit(session, "run_queued", "A manual research run was queued", topic_id=topic_id)
    session.commit()
    session.refresh(run)
    return run


@router.get("/runs/{run_id}", response_model=ResearchRunRead)
def get_run(run_id: str, session: Session = Depends(get_session)) -> ResearchRun:
    return get_or_404(session, ResearchRun, run_id)


@router.get("/topics/{topic_id}/research-drafts", response_model=list[ResearchDraftSummary])
def list_research_drafts(
    topic_id: str, session: Session = Depends(get_session)
) -> list[ResearchDraft]:
    get_or_404(session, Topic, topic_id)
    statement = (
        select(ResearchDraft)
        .where(ResearchDraft.topic_id == topic_id)
        .order_by(ResearchDraft.created_at.desc())
    )
    return list(session.scalars(statement))


@router.get("/research-drafts/{draft_id}", response_model=ResearchDraftDetail)
def get_research_draft(
    draft_id: str, session: Session = Depends(get_session)
) -> ResearchDraftDetail:
    draft = get_or_404(session, ResearchDraft, draft_id)
    claims = list(
        session.scalars(select(CandidateClaim).where(CandidateClaim.draft_id == draft.id))
    )
    connections = list(
        session.scalars(select(CandidateConnection).where(CandidateConnection.draft_id == draft.id))
    )
    insights = list(
        session.scalars(select(CandidateInsight).where(CandidateInsight.draft_id == draft.id))
    )
    leads = list(session.scalars(select(SearchLead).where(SearchLead.draft_id == draft.id)))
    return ResearchDraftDetail(
        **ResearchDraftSummary.model_validate(draft).model_dump(),
        claims=[CandidateClaimRead.model_validate(item) for item in claims],
        connections=[CandidateConnectionRead.model_validate(item) for item in connections],
        insights=[CandidateInsightRead.model_validate(item) for item in insights],
        leads=[SearchLeadRead.model_validate(item) for item in leads],
    )


@router.post("/research-drafts/{draft_id}/verify", response_model=ResearchRunRead, status_code=202)
def verify_research_draft(draft_id: str, session: Session = Depends(get_session)) -> ResearchRun:
    draft = get_or_404(session, ResearchDraft, draft_id)
    active = session.scalar(
        select(ResearchRun).where(
            ResearchRun.draft_id == draft.id,
            ResearchRun.kind == "verify",
            ResearchRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    )
    if active:
        return active

    run = ResearchRun(
        topic_id=draft.topic_id,
        draft_id=draft.id,
        trigger="manual",
        kind="verify",
    )
    session.add(run)
    add_audit(
        session,
        "verification_queued",
        "A browser research draft was queued for confirmation",
        topic_id=draft.topic_id,
        details={"draft_id": draft.id},
    )
    session.commit()
    session.refresh(run)
    return run


@router.get("/research-drafts/{draft_id}/verification", response_model=list[VerificationResultRead])
def get_draft_verification(
    draft_id: str, session: Session = Depends(get_session)
) -> list[VerificationResult]:
    get_or_404(session, ResearchDraft, draft_id)
    claim_ids = select(CandidateClaim.id).where(CandidateClaim.draft_id == draft_id)
    statement = (
        select(VerificationResult)
        .where(VerificationResult.claim_id.in_(claim_ids))
        .order_by(VerificationResult.created_at.desc())
    )
    return list(session.scalars(statement))


@router.get("/topics/{topic_id}/candidate-insights", response_model=list[CandidateInsightRead])
def list_candidate_insights(
    topic_id: str, session: Session = Depends(get_session)
) -> list[CandidateInsight]:
    get_or_404(session, Topic, topic_id)
    statement = (
        select(CandidateInsight)
        .where(CandidateInsight.topic_id == topic_id)
        .order_by(CandidateInsight.created_at.desc())
    )
    return list(session.scalars(statement))


@router.patch("/candidate-insights/{insight_id}", response_model=CandidateInsightRead)
def review_candidate_insight(
    insight_id: str,
    payload: CandidateInsightPatch,
    session: Session = Depends(get_session),
) -> CandidateInsight:
    insight = get_or_404(session, CandidateInsight, insight_id)
    insight.review_status = payload.review_status
    session.commit()
    session.refresh(insight)
    return insight


@router.get("/source-catalog", response_model=list[SourceCatalogRead])
def list_source_catalog(
    category: str | None = None,
    session: Session = Depends(get_session),
) -> list[SourceCatalogEntry]:
    statement = select(SourceCatalogEntry).order_by(
        SourceCatalogEntry.category, SourceCatalogEntry.publisher
    )
    if category:
        statement = statement.where(SourceCatalogEntry.category == category)
    return list(session.scalars(statement))


@router.post("/source-catalog/custom", response_model=SourceCatalogRead, status_code=201)
def create_custom_source(
    payload: SourceCatalogCreate, session: Session = Depends(get_session)
) -> SourceCatalogEntry:
    if session.get(SourceCatalogEntry, payload.id):
        raise HTTPException(status_code=409, detail="Source identifier already exists")
    source = SourceCatalogEntry(**payload.model_dump(), is_builtin=False)
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@router.patch("/source-catalog/{source_id}", response_model=SourceCatalogRead)
def update_source_catalog(
    source_id: str,
    payload: SourceCatalogPatch,
    session: Session = Depends(get_session),
) -> SourceCatalogEntry:
    source = get_or_404(session, SourceCatalogEntry, source_id)
    changes = payload.model_dump(exclude_unset=True)
    if "allowed_paths" in changes:
        validated = SourceCatalogCreate(
            id=source.id,
            publisher=source.publisher,
            hostname=source.hostname,
            allowed_paths=changes["allowed_paths"],
            category=source.category,
            topic_tags=source.topic_tags,
            evidence_role=source.evidence_role,
            access_mode=source.access_mode,
            approval_reason=source.approval_reason,
            reviewed_at=source.reviewed_at,
            is_enabled=changes.get("is_enabled", source.is_enabled),
        )
        changes["allowed_paths"] = validated.allowed_paths
    for key, value in changes.items():
        setattr(source, key, value)
    source.reviewed_at = datetime.now().astimezone()
    session.commit()
    session.refresh(source)
    return source


@router.get("/topics/{topic_id}/graph", response_model=GraphResponse)
def get_topic_graph(
    topic_id: str,
    limit: int = Query(default=500, ge=1, le=500),
    session: Session = Depends(get_session),
) -> GraphResponse:
    get_or_404(session, Topic, topic_id)
    claims = list(
        session.scalars(
            select(CandidateClaim)
            .where(
                CandidateClaim.topic_id == topic_id,
                CandidateClaim.status.in_([KnowledgeStatus.CONFIRMED, KnowledgeStatus.CONTESTED]),
            )
            .limit(limit)
        )
    )
    remaining = max(0, limit - len(claims))
    concepts = list(
        session.scalars(select(Concept).where(Concept.topic_id == topic_id).limit(remaining))
    )
    remaining = max(0, remaining - len(concepts))
    insights = list(
        session.scalars(
            select(CandidateInsight)
            .where(
                CandidateInsight.topic_id == topic_id,
                CandidateInsight.verification_status != KnowledgeStatus.UNVERIFIED,
            )
            .limit(remaining)
        )
    )

    nodes = [
        GraphNode(id=claim.id, kind="claim", label=claim.statement, status=claim.status)
        for claim in claims
    ]
    nodes.extend(
        GraphNode(id=concept.id, kind="concept", label=concept.name, status="confirmed")
        for concept in concepts
    )
    nodes.extend(
        GraphNode(
            id=insight.id,
            kind="hypothesis",
            label=insight.title,
            status=insight.verification_status,
            details={"review_status": insight.review_status, "confidence": insight.confidence},
        )
        for insight in insights
    )
    node_ids = {node.id for node in nodes}
    edges = list(session.scalars(select(GraphEdge).where(GraphEdge.topic_id == topic_id)))
    edge_reads = [
        GraphEdgeRead(
            id=edge.id,
            source=edge.source_id,
            target=edge.target_id,
            relationship=edge.relationship,
            status=edge.status,
        )
        for edge in edges
        if edge.source_id in node_ids and edge.target_id in node_ids
    ]
    return GraphResponse(nodes=nodes, edges=edge_reads)

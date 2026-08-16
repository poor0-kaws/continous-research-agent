from datetime import datetime
from ipaddress import ip_address
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

KnowledgeState = Literal[
    "pending",
    "confirmed",
    "partially_confirmed",
    "contested",
    "unverified",
    "rejected",
]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TopicCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    question: str = Field(min_length=10, max_length=2_000)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    enabled_source_ids: list[str] = Field(default_factory=list)
    rss_feed_urls: list[str] = Field(default_factory=list, max_length=20)
    schedule_hour: int = Field(default=3, ge=0, le=23)
    timezone: str = Field(default="America/New_York", max_length=80)

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})

    @field_validator("rss_feed_urls")
    @classmethod
    def clean_feed_urls(cls, values: list[str]) -> list[str]:
        return sorted({str(HttpUrl(value)) for value in values})


class TopicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    question: str | None = Field(default=None, min_length=10, max_length=2_000)
    keywords: list[str] | None = None
    enabled_source_ids: list[str] | None = None
    rss_feed_urls: list[str] | None = None
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    timezone: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None


class TopicRead(OrmModel):
    id: str
    title: str
    question: str
    keywords: list[str]
    enabled_source_ids: list[str]
    rss_feed_urls: list[str]
    schedule_hour: int
    timezone: str
    is_active: bool
    next_run_at: datetime | None
    created_at: datetime


class SourceCatalogCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,99}$")
    publisher: str = Field(min_length=2, max_length=200)
    hostname: str = Field(min_length=4, max_length=255)
    allowed_paths: list[str] = Field(default_factory=lambda: ["/"])
    category: str
    topic_tags: list[str] = Field(default_factory=list)
    evidence_role: Literal["primary", "secondary", "discovery_only"]
    access_mode: Literal["full_text", "abstract_only", "metadata_only", "discovery_only"]
    approval_reason: str = Field(min_length=10)
    reviewed_at: datetime
    is_enabled: bool = True

    @field_validator("hostname")
    @classmethod
    def exact_hostname_only(cls, value: str) -> str:
        cleaned = value.lower().strip().rstrip(".")
        if "*" in cleaned or ":" in cleaned or "/" in cleaned:
            raise ValueError("Use one exact hostname without wildcards, ports, or paths")
        if cleaned == "localhost" or "." not in cleaned:
            raise ValueError("Use a public hostname, not a local computer name")
        try:
            ip_address(cleaned)
        except ValueError:
            return cleaned
        raise ValueError("Use a public hostname, not a direct IP address")

    @field_validator("allowed_paths")
    @classmethod
    def paths_start_with_slash(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("At least one allowed path is required")
        if any(not value.startswith("/") or "*" in value for value in values):
            raise ValueError("Paths must start with / and cannot contain wildcards")
        return sorted(set(values))


class SourceCatalogPatch(BaseModel):
    is_enabled: bool | None = None
    allowed_paths: list[str] | None = None


class SourceCatalogRead(OrmModel):
    id: str
    publisher: str
    hostname: str
    allowed_paths: list[str]
    category: str
    topic_tags: list[str]
    evidence_role: str
    access_mode: str
    approval_reason: str
    reviewed_at: datetime
    is_enabled: bool
    is_builtin: bool


class ResearchRunRead(OrmModel):
    id: str
    topic_id: str
    draft_id: str | None
    kind: str
    trigger: str
    status: str
    progress_stage: str
    error_message: str | None
    documents_processed: int
    model_requests: int
    attempt_count: int
    max_attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CandidateClaimRead(OrmModel):
    id: str
    statement: str
    citation_urls: list[str]
    status: str
    importance: str
    published_at: datetime | None


class CandidateConnectionRead(OrmModel):
    id: str
    source_label: str
    target_label: str
    relationship: str
    rationale: str
    status: str


class CandidateInsightRead(OrmModel):
    id: str
    title: str
    explanation: str
    supporting_claim_ids: list[str]
    conflicting_claim_ids: list[str]
    confidence: str
    verification_status: str
    review_status: str


class CandidateInsightPatch(BaseModel):
    review_status: Literal["draft", "useful", "rejected"]


class SearchLeadRead(OrmModel):
    id: str
    title: str
    url: str
    publisher: str
    access_mode: str
    status: str


class ResearchDraftSummary(OrmModel):
    id: str
    topic_id: str
    report_text: str
    status: str
    searched_domains: list[str]
    cited_urls: list[str]
    model_name: str
    created_at: datetime


class ResearchDraftDetail(ResearchDraftSummary):
    claims: list[CandidateClaimRead]
    connections: list[CandidateConnectionRead]
    insights: list[CandidateInsightRead]
    leads: list[SearchLeadRead]


class VerificationResultRead(OrmModel):
    id: str
    claim_id: str
    status: str
    rationale: str
    supporting_source_count: int
    conflicting_source_count: int
    source_independence: float
    created_at: datetime


class GraphNode(BaseModel):
    id: str
    kind: Literal["claim", "concept", "hypothesis"]
    label: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeRead(BaseModel):
    id: str
    source: str
    target: str
    relationship: str
    status: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdgeRead]


class GroqSearchResult(BaseModel):
    title: str
    url: HttpUrl
    content: str = ""
    score: float = 0.0


class ParsedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str
    citation_urls: list[str]
    importance: Literal["normal", "important"]


class ParsedConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_label: str
    target_label: str
    relationship: Literal["supports", "contradicts", "about", "similar_to"]
    rationale: str


class ParsedInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    explanation: str
    supporting_claim_numbers: list[int]


class ParsedDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ParsedClaim]
    connections: list[ParsedConnection]
    insights: list[ParsedInsight]


class VerifiedExcerpt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    excerpt: str
    locator: str
    stance: Literal["supports", "conflicts"]


class ClaimVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: KnowledgeState
    rationale: str
    excerpts: list[VerifiedExcerpt]

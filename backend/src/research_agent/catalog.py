from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.models import SourceCatalogEntry, Topic
from research_agent.schemas import SourceCatalogCreate

BASELINE_CATEGORIES = {"scholarly-index", "government", "public-data"}


def load_catalog_file(path: Path) -> list[SourceCatalogCreate]:
    with path.open(encoding="utf-8") as catalog_file:
        raw_catalog = yaml.safe_load(catalog_file) or {}

    return [SourceCatalogCreate.model_validate(item) for item in raw_catalog.get("sources", [])]


def seed_catalog(session: Session, path: Path) -> int:
    if not path.exists():
        return 0

    inserted = 0
    for source in load_catalog_file(path):
        existing = session.get(SourceCatalogEntry, source.id)
        values = source.model_dump()
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            continue

        session.add(SourceCatalogEntry(**values, is_builtin=True))
        inserted += 1

    session.commit()
    return inserted


def enabled_sources_for_topic(session: Session, topic: Topic) -> list[SourceCatalogEntry]:
    statement = select(SourceCatalogEntry).where(SourceCatalogEntry.is_enabled.is_(True))
    sources = list(session.scalars(statement))
    if not topic.enabled_source_ids:
        return sources

    enabled = set(topic.enabled_source_ids)
    return [source for source in sources if source.id in enabled]


def choose_relevant_sources(
    topic: Topic, sources: Iterable[SourceCatalogEntry]
) -> list[SourceCatalogEntry]:
    topic_terms = {term.lower() for term in [topic.title, *topic.keywords]}
    selected: list[SourceCatalogEntry] = []

    for source in sources:
        tags = {tag.lower() for tag in source.topic_tags}
        if source.category in BASELINE_CATEGORIES or topic_terms & tags:
            selected.append(source)

    if selected:
        return selected

    return list(sources)


def group_domain_batches(
    sources: Iterable[SourceCatalogEntry], batch_size: int = 12
) -> list[list[str]]:
    by_category: dict[str, list[str]] = {}
    for source in sources:
        by_category.setdefault(source.category, []).append(source.hostname)

    batches: list[list[str]] = []
    for domains in by_category.values():
        unique_domains = sorted(set(domains))
        for start in range(0, len(unique_domains), batch_size):
            batches.append(unique_domains[start : start + batch_size])
    return batches


def reviewed_now() -> datetime:
    return datetime.now(UTC)

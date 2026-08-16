from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.catalog import group_domain_batches, load_catalog_file
from research_agent.config import Settings
from research_agent.schemas import SourceCatalogCreate

CATALOG = Path(__file__).resolve().parents[2] / "config" / "source_catalog.yaml"


def test_default_settings_point_to_the_real_catalog() -> None:
    assert Settings().source_catalog_path == CATALOG
    assert Settings().source_catalog_path.exists()


def test_builtin_catalog_contains_at_least_one_hundred_exact_rules() -> None:
    sources = load_catalog_file(CATALOG)

    assert len(sources) >= 100
    assert all("*" not in source.hostname for source in sources)
    assert len({source.id for source in sources}) == len(sources)


def test_paywalled_publications_are_discovery_only() -> None:
    sources = {source.id: source for source in load_catalog_file(CATALOG)}

    for source_id in ("financial-times", "wall-street-journal", "economist"):
        assert sources[source_id].access_mode == "discovery_only"
        assert sources[source_id].evidence_role == "discovery_only"


def test_custom_source_rejects_wildcard_domains() -> None:
    with pytest.raises(ValidationError):
        SourceCatalogCreate(
            id="all-universities",
            publisher="Every university",
            hostname="*.edu",
            allowed_paths=["/"],
            category="university",
            topic_tags=[],
            evidence_role="secondary",
            access_mode="full_text",
            approval_reason="This should never be accepted",
            reviewed_at="2026-08-16T00:00:00Z",
        )


@pytest.mark.parametrize("hostname", ["localhost", "127.0.0.1", "10.0.0.1"])
def test_custom_source_rejects_local_hosts(hostname: str) -> None:
    with pytest.raises(ValidationError):
        SourceCatalogCreate(
            id="unsafe-local-source",
            publisher="Unsafe Local Source",
            hostname=hostname,
            allowed_paths=["/"],
            category="custom",
            topic_tags=[],
            evidence_role="secondary",
            access_mode="full_text",
            approval_reason="This must never reach a private network",
            reviewed_at="2026-08-16T00:00:00Z",
        )


def test_domain_batches_are_small_and_grouped() -> None:
    sources = load_catalog_file(CATALOG)[:30]
    batches = group_domain_batches(sources)

    assert batches
    assert all(len(batch) <= 6 for batch in batches)

import pytest

from research_agent.discovery import DiscoveryClient
from research_agent.models import SourceCatalogEntry
from research_agent.security import SourceSafetyError


def metadata_source(source_id: str, hostname: str) -> SourceCatalogEntry:
    return SourceCatalogEntry(
        id=source_id,
        publisher=source_id.title(),
        hostname=hostname,
        allowed_paths=["/"],
        category="scholarly-index",
        topic_tags=["research"],
        evidence_role="secondary",
        access_mode="metadata_only",
        approval_reason="A metadata source used by this isolated test",
        reviewed_at="2026-08-16T00:00:00Z",
    )


def test_scholarly_api_records_remain_metadata_only_leads() -> None:
    client = DiscoveryClient()
    openalex = metadata_source("openalex", "api.openalex.org")
    crossref = metadata_source("crossref", "api.crossref.org")

    openalex_leads = client._parse_openalex(  # noqa: SLF001
        {"results": [{"id": "https://api.openalex.org/works/W1", "title": "Study one"}]},
        openalex,
    )
    crossref_leads = client._parse_crossref(  # noqa: SLF001
        {"message": {"items": [{"DOI": "10.1000/example", "title": ["Study two"]}]}},
        crossref,
    )

    assert openalex_leads[0].access_mode == "metadata_only"
    assert crossref_leads[0].url.startswith("https://api.crossref.org/works/")


def test_rss_feed_cannot_smuggle_an_unapproved_link() -> None:
    client = DiscoveryClient()
    source = metadata_source("approved-news", "approved.example")
    unsafe_feed = """
        <rss><channel><item><title>Unsafe</title>
        <link>https://attacker.example/article/1</link></item></channel></rss>
    """

    with pytest.raises(SourceSafetyError):
        client._parse_rss(unsafe_feed, source)  # noqa: SLF001

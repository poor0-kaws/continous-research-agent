import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import httpx

from research_agent.models import SourceCatalogEntry, Topic
from research_agent.security import (
    SourceSafetyError,
    assert_public_hostname,
    normalize_url,
    source_for_url,
)


@dataclass(frozen=True)
class DiscoveryLead:
    title: str
    url: str
    publisher: str
    access_mode: str


class DiscoveryClient:
    """Find metadata leads. Nothing returned here is trusted evidence."""

    def __init__(self, timeout_seconds: float = 15.0, max_bytes: int = 1_000_000):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def discover(self, topic: Topic, sources: list[SourceCatalogEntry]) -> list[DiscoveryLead]:
        leads: list[DiscoveryLead] = []
        queries = [
            (
                "https://api.openalex.org/works"
                f"?search={quote(topic.question)}&per-page=5&select=id,title",
                self._parse_openalex,
            ),
            (
                "https://api.crossref.org/works"
                f"?query={quote(topic.question)}&rows=5&select=DOI,title",
                self._parse_crossref,
            ),
        ]

        for url, parser in queries:
            try:
                source, response = self._get(url, sources)
                leads.extend(parser(response.json(), source))
            except (SourceSafetyError, httpx.HTTPError, ValueError):
                continue

        for feed_url in topic.rss_feed_urls:
            try:
                source, response = self._get(str(feed_url), sources)
                leads.extend(self._parse_rss(response.text, source))
            except (ET.ParseError, SourceSafetyError, httpx.HTTPError, ValueError):
                continue

        unique = {lead.url: lead for lead in leads}
        return list(unique.values())[:25]

    def _get(
        self, url: str, sources: list[SourceCatalogEntry]
    ) -> tuple[SourceCatalogEntry, httpx.Response]:
        normalized = normalize_url(url)
        source = source_for_url(normalized, sources)
        hostname = urlsplit(normalized).hostname
        if hostname is None:
            raise SourceSafetyError("Discovery URL has no hostname")
        assert_public_hostname(hostname)
        response = httpx.get(
            normalized,
            follow_redirects=False,
            timeout=self.timeout_seconds,
            headers={"User-Agent": "ContResAI/0.1 (metadata discovery)"},
        )
        if response.is_redirect:
            raise SourceSafetyError("Discovery endpoints cannot redirect")
        response.raise_for_status()
        if len(response.content) > self.max_bytes:
            raise SourceSafetyError("Discovery response exceeded the safe size limit")
        return source, response

    def _parse_openalex(self, payload: dict, source: SourceCatalogEntry) -> list[DiscoveryLead]:
        leads: list[DiscoveryLead] = []
        for item in payload.get("results", []):
            work_id = str(item.get("id", ""))
            if not work_id.startswith("https://api.openalex.org/works/"):
                continue
            leads.append(
                DiscoveryLead(
                    title=str(item.get("title") or "Untitled OpenAlex record")[:1_000],
                    url=work_id,
                    publisher=source.publisher,
                    access_mode=source.access_mode,
                )
            )
        return leads

    def _parse_crossref(self, payload: dict, source: SourceCatalogEntry) -> list[DiscoveryLead]:
        leads: list[DiscoveryLead] = []
        for item in payload.get("message", {}).get("items", []):
            doi = str(item.get("DOI", "")).strip()
            if not doi:
                continue
            titles = item.get("title") or ["Untitled Crossref record"]
            leads.append(
                DiscoveryLead(
                    title=str(titles[0])[:1_000],
                    url=f"https://api.crossref.org/works/{quote(doi, safe='')}",
                    publisher=source.publisher,
                    access_mode=source.access_mode,
                )
            )
        return leads

    def _parse_rss(self, xml_text: str, source: SourceCatalogEntry) -> list[DiscoveryLead]:
        root = ET.fromstring(xml_text)
        leads: list[DiscoveryLead] = []
        entries = [*root.findall(".//item"), *root.findall(".//{*}entry")]
        for entry in entries[:25]:
            title = entry.findtext("title") or entry.findtext("{*}title") or "Untitled feed item"
            link = entry.findtext("link") or entry.findtext("{*}link")
            if not link:
                link_element = entry.find("{*}link")
                link = link_element.get("href") if link_element is not None else None
            if not link:
                continue
            normalized = normalize_url(link)
            source_for_url(normalized, [source])
            leads.append(
                DiscoveryLead(
                    title=title.strip()[:1_000],
                    url=normalized,
                    publisher=source.publisher,
                    access_mode=source.access_mode,
                )
            )
        return leads

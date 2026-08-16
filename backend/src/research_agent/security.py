import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import trafilatura
from bs4 import BeautifulSoup

from research_agent.models import SourceCatalogEntry

PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all|any|the|your)?\s*(previous|prior|above)\s+instructions",
        r"system\s+prompt",
        r"reveal\s+(your|the)\s+(instructions|prompt|secrets)",
        r"act\s+as\s+(an?|the)\s+.*assistant",
        r"do\s+not\s+follow\s+.*instructions",
        r"developer\s+message",
        r"tool\s+call",
    )
]


class SourceSafetyError(ValueError):
    pass


@dataclass(frozen=True)
class SafeDocument:
    url: str
    title: str
    text: str
    content_hash: str
    source: SourceCatalogEntry


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() != "https":
        raise SourceSafetyError("Only HTTPS sources are allowed")
    if parsed.username or parsed.password:
        raise SourceSafetyError("Source URLs cannot contain credentials")
    if parsed.port not in (None, 443):
        raise SourceSafetyError("Source URLs cannot use custom ports")
    if not parsed.hostname:
        raise SourceSafetyError("Source URL has no hostname")

    clean_path = parsed.path or "/"
    return urlunsplit(("https", parsed.hostname.lower(), clean_path, parsed.query, ""))


def source_for_url(url: str, sources: list[SourceCatalogEntry]) -> SourceCatalogEntry:
    normalized = normalize_url(url)
    parsed = urlsplit(normalized)
    for source in sources:
        if parsed.hostname != source.hostname:
            continue
        if any(parsed.path.startswith(prefix) for prefix in source.allowed_paths):
            return source
    raise SourceSafetyError("URL is not covered by an approved source rule")


def assert_public_hostname(hostname: str) -> None:
    try:
        records = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise SourceSafetyError("Source hostname could not be resolved") from error

    if not records:
        raise SourceSafetyError("Source hostname returned no addresses")

    for record in records:
        address = ipaddress.ip_address(record[4][0])
        if not address.is_global:
            raise SourceSafetyError("Source resolved to a private or special address")


def contains_prompt_injection(text: str) -> bool:
    sample = text[:200_000]
    return any(pattern.search(sample) for pattern in PROMPT_INJECTION_PATTERNS)


def sanitize_html(content: str) -> tuple[str, str]:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "form", "nav"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled source"
    extracted = trafilatura.extract(str(soup), include_comments=False, include_tables=False)
    if extracted:
        return title[:500], extracted.strip()
    return title[:500], soup.get_text("\n", strip=True)


class GuardedFetcher:
    def __init__(self, max_bytes: int = 2_000_000, timeout_seconds: float = 15.0):
        self.max_bytes = max_bytes
        self.timeout_seconds = timeout_seconds

    def fetch(self, url: str, sources: list[SourceCatalogEntry]) -> SafeDocument:
        current_url = normalize_url(url)

        for _ in range(4):
            source = source_for_url(current_url, sources)
            if source.access_mode in {"discovery_only", "metadata_only"}:
                raise SourceSafetyError("This source is approved for discovery metadata only")

            hostname = urlsplit(current_url).hostname
            if not hostname:
                raise SourceSafetyError("Source URL has no hostname")
            assert_public_hostname(hostname)

            response = httpx.get(
                current_url,
                follow_redirects=False,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "ContResAI/0.1 (guarded research fetcher)"},
            )
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SourceSafetyError("Redirect response did not include a location")
                current_url = normalize_url(urljoin(current_url, location))
                continue

            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            allowed_type = any(
                value in content_type
                for value in ("text/html", "text/plain", "application/xhtml+xml", "application/xml")
            )
            if not allowed_type:
                raise SourceSafetyError("Source returned an unsupported content type")
            if len(response.content) > self.max_bytes:
                raise SourceSafetyError("Source response was larger than the safe limit")

            title, text = sanitize_html(response.text)
            if len(text) < 80:
                raise SourceSafetyError("Source did not contain enough readable text")
            if contains_prompt_injection(text):
                raise SourceSafetyError("Source contains likely prompt-injection instructions")

            content_hash = hashlib.sha256(text.encode()).hexdigest()
            return SafeDocument(current_url, title, text, content_hash, source)

        raise SourceSafetyError("Source redirected too many times")

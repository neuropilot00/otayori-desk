from __future__ import annotations

import random
import ipaddress
import re
import socket
import time
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

import requests


class FetchError(RuntimeError):
    """Raised when a source page or document cannot be fetched safely."""


@dataclass(frozen=True)
class LinkCandidate:
    url: str
    title: str
    kind: str


@dataclass(frozen=True)
class FetchedDocument:
    url: str
    content: bytes | None
    content_type: str
    etag: str | None
    last_modified: str | None
    not_modified: bool = False


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a" or self._href is not None:
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join(self._text)))
            self._href = None
            self._text = []


def _clean_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()


def parse_relevant_links(html: str, page_url: str) -> list[LinkCandidate]:
    parser = _AnchorParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:
        raise FetchError("could not parse the school page HTML") from exc

    result: list[LinkCandidate] = []
    seen: set[str] = set()
    page_without_fragment = urldefrag(page_url)[0]
    for href, raw_title in parser.anchors:
        absolute_url = urldefrag(urljoin(page_url, href))[0]
        parsed_url = urlparse(absolute_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            continue
        if absolute_url == page_without_fragment:
            continue
        title = _clean_title(raw_title)
        lower_url = absolute_url.lower()
        is_pdf = parsed_url.path.lower().endswith(".pdf") or ".pdf?" in lower_url
        has_school_label = "学校だより" in title
        has_grade_label = "学年だより" in title
        if not (is_pdf or has_school_label or has_grade_label):
            continue
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        if has_grade_label:
            kind = "grade_news"
        elif has_school_label:
            kind = "school_news"
        else:
            kind = "document"
        result.append(LinkCandidate(url=absolute_url, title=title or absolute_url.rsplit("/", 1)[-1], kind=kind))
    return result


class HttpFetcher:
    TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        timeout_seconds: float = 30,
        max_document_bytes: int = 10_000_000,
        user_agent: str = "sakurano-line-notifier/1.0",
        session: requests.Session | None = None,
        max_attempts: int = 4,
        allowed_hosts: set[str] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_document_bytes = max_document_bytes
        self.session = session or requests.Session()
        if session is None:
            self.session.trust_env = False
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "ja,en;q=0.8"})
        self.max_attempts = max_attempts
        self.allowed_hosts = {str(host).lower() for host in allowed_hosts} if allowed_hosts else None

    def _validate_url(self, url: str) -> None:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
                raise ValueError("invalid URL")
            host = parsed.hostname.lower()
            if self.allowed_hosts is not None and host not in self.allowed_hosts:
                raise ValueError("host is not in the reviewed source registry")
            addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                raise ValueError("non-public network address")
        except (ValueError, OSError) as exc:
            raise FetchError("source URL is not an allowed public address") from exc

    def _request(self, url: str, headers: dict[str, str] | None = None, stream: bool = False) -> requests.Response:
        request_headers = dict(headers or {})
        for attempt in range(self.max_attempts):
            try:
                current_url = url
                for redirect in range(6):
                    self._validate_url(current_url)
                    response = self.session.get(
                        current_url,
                        headers=request_headers,
                        timeout=(5, self.timeout_seconds),
                        stream=True,
                        allow_redirects=False,
                    )
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        break
                    location = response.headers.get("Location")
                    response.close()
                    if not location or redirect == 5:
                        raise FetchError("invalid or excessive source redirects")
                    destination = urljoin(current_url, location)
                    if current_url.startswith("https://") and not destination.startswith("https://"):
                        raise FetchError("HTTPS downgrade is not allowed")
                    current_url = destination
            except requests.RequestException as exc:
                if attempt == self.max_attempts - 1:
                    raise FetchError(f"request failed for {url}: {exc.__class__.__name__}") from exc
                self._backoff(attempt)
                continue

            if response.status_code not in self.TRANSIENT_STATUS_CODES:
                return response
            response.close()
            if attempt == self.max_attempts - 1:
                raise FetchError(f"source returned HTTP {response.status_code}: {url}")
            self._backoff(attempt, response.headers.get("Retry-After"))
        raise FetchError(f"request failed for {url}")

    def _bounded_payload(self, response: requests.Response, limit: int) -> bytes:
        chunks: list[bytes] = []
        total = 0
        deadline = time.monotonic() + self.timeout_seconds
        try:
            length = response.headers.get("Content-Length")
            if length and length.isdecimal() and int(length) > limit:
                raise FetchError("source response exceeds size limit")
            for chunk in response.iter_content(chunk_size=65_536):
                total += len(chunk)
                if total > limit or time.monotonic() > deadline:
                    raise FetchError("source response exceeds size or time limit")
                chunks.append(chunk)
            return b"".join(chunks)
        except requests.RequestException as exc:
            raise FetchError("source response could not be read") from exc
        finally:
            response.close()

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None = None) -> None:
        try:
            server_delay = float(retry_after) if retry_after else 0.0
        except ValueError:
            server_delay = 0.0
        server_delay = min(30.0, max(0.0, server_delay))
        delay = max(server_delay, min(30.0, (2**attempt) + random.uniform(0, 0.25)))
        time.sleep(delay)

    def fetch_page(self, url: str) -> str:
        response = self._request(url)
        try:
            if response.status_code < 200 or response.status_code >= 300:
                raise FetchError(f"source page returned HTTP {response.status_code}: {url}")
            payload = self._bounded_payload(response, min(self.max_document_bytes, 2_000_000))
            response._content = payload
            content_type = response.headers.get("Content-Type", "").lower()
            # Some Japanese school CMSs omit charset and requests falls back to
            # ISO-8859-1 even when the HTML declares UTF-8 in a meta tag.
            # apparent_encoding is a safer fallback for that specific case.
            encoding = response.encoding or response.apparent_encoding or "utf-8"
            if "text/html" in content_type and "charset=" not in content_type and response.apparent_encoding:
                encoding = response.apparent_encoding
            return payload.decode(encoding, errors="replace")
        finally:
            response.close()

    def fetch_document(self, url: str, conditional_headers: dict[str, str] | None = None) -> FetchedDocument:
        response = self._request(url, headers=conditional_headers, stream=True)
        if response.status_code == 304:
            response.close()
            return FetchedDocument(url, None, "", None, None, not_modified=True)
        if response.status_code < 200 or response.status_code >= 300:
            status = response.status_code
            response.close()
            raise FetchError(f"document returned HTTP {status}: {url}")

        content_type = response.headers.get("Content-Type", "")
        etag = response.headers.get("ETag")
        last_modified = response.headers.get("Last-Modified")
        payload = self._bounded_payload(response, self.max_document_bytes)
        return FetchedDocument(url, payload, content_type, etag, last_modified)

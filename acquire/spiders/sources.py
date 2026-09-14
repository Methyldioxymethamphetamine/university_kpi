"""The one spider. Both registry entry types (pattern, adhoc_url) share this
single fetch path (PROMPTS.md P2A): SourceRegistry hands it fully-built
scrapy.Request objects, and this spider does nothing but dispatch to
save_raw (direct fetch) or parse_discovery (the WordPress-media-API style
search-then-follow fetch) and turn a response into an item for
ManifestPipeline. It never opens a PDF, never parses HTML for content, and
never imports Docling -- P-3.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import scrapy
from scrapy.exceptions import IgnoreRequest

from acquire.manifestlog import find_by_url, record_blocked
from acquire.registry import SourceRegistry, resolved_for_year


def _normalize(s: str) -> str:
    """Fold whitespace/dash/underscore variants for matching a title string
    the WordPress API already handed us as structured JSON. This is
    bookkeeping on a field, not interpretation of a document's content."""
    return re.sub(r"[\s_-]+", " ", s or "").strip().lower()


def _header(response: scrapy.http.Response, name: str) -> str | None:
    value = response.headers.get(name)
    return value.decode("latin-1") if value is not None else None


def _attach_conditional_headers(request: scrapy.Request, prior: dict | None) -> None:
    if not prior:
        return
    if prior.get("etag"):
        request.headers[b"If-None-Match"] = prior["etag"].encode("latin-1")
    if prior.get("last_modified"):
        request.headers[b"If-Modified-Since"] = prior["last_modified"].encode("latin-1")


class SourceSpider(scrapy.Spider):
    name = "sources"

    def __init__(self, run_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.run_id = run_id
        self.registry = SourceRegistry.from_yaml_glob()

    async def start(self):
        # Scrapy >= 2.13 entry point (replaces the old sync
        # start_requests()); this project pins scrapy>=2.14 in
        # pyproject.toml so this is the one that actually runs.
        for request in self.registry.build_requests(self):
            target = request.meta["target"]
            url_for_lookup = request.meta["target"].url or request.meta["target"].discovery_url
            prior = find_by_url(url_for_lookup)
            request.meta["prior_sha256"] = prior["sha256"] if prior else None
            _attach_conditional_headers(request, prior)
            yield request

    def parse_discovery(self, response: scrapy.http.Response):
        target = response.meta["target"]
        try:
            items = json.loads(response.body)
        except json.JSONDecodeError:
            self.logger.error("discovery response for %s was not JSON: %s", target.source_id, response.url)
            record_blocked(target, response.url, reason="discovery response not JSON", run_id=self.run_id)
            return

        by_title = []
        for entry in items:
            raw_title = entry.get("title")
            title = raw_title.get("rendered", raw_title) if isinstance(raw_title, dict) else raw_title
            by_title.append((title or "", entry.get("source_url")))

        for match in target.discovery_matches:
            year = match["year"]
            wanted = _normalize(match["title_contains"])
            hits = [(t, u) for t, u in by_title if wanted in _normalize(t)]
            if len(hits) != 1:
                self.logger.error(
                    "discovery match failure for %s year=%s wanted=%r hits=%d",
                    target.source_id, year, match["title_contains"], len(hits),
                )
                self.crawler.stats.inc_value("acquisition/discovery_match_failed")
                record_blocked(
                    target,
                    response.url,
                    reason=f"discovery match failure: wanted={match['title_contains']!r} hits={len(hits)}",
                    run_id=self.run_id,
                )
                continue

            _title, url = hits[0]
            child = resolved_for_year(target, year, url)
            prior = find_by_url(url)
            request = scrapy.Request(
                url,
                callback=self.save_raw,
                errback=self.on_request_error,
                meta={"target": child, "prior_sha256": prior["sha256"] if prior else None},
            )
            _attach_conditional_headers(request, prior)
            yield request

    def save_raw(self, response: scrapy.http.Response):
        target = response.meta["target"]
        yield {
            "target": target,
            "url": response.url,
            "http_status": response.status,
            "etag": _header(response, "ETag"),
            "last_modified": _header(response, "Last-Modified"),
            "content_type": _header(response, "Content-Type"),
            "body": None if response.status == 304 else bytes(response.body),
            "prior_sha256": response.meta.get("prior_sha256"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
        }

    def on_request_error(self, failure):
        target = failure.request.meta.get("target")
        source_id = getattr(target, "source_id", None) or "?"
        if failure.check(IgnoreRequest):
            # Includes robots.txt denials (Scrapy's RobotsTxtMiddleware
            # raises IgnoreRequest for a disallowed URL). STOP CONDITION:
            # report it, never silently skip the institution.
            self.logger.error("BLOCKED by policy: %s -> %s (%s)", source_id, failure.request.url, failure.value)
            self.crawler.stats.inc_value("acquisition/blocked_by_policy")
            record_blocked(target, failure.request.url, reason=f"IgnoreRequest: {failure.value}", run_id=self.run_id)
        else:
            self.logger.error("FETCH ERROR: %s -> %s (%s)", source_id, failure.request.url, failure.value)
            self.crawler.stats.inc_value("acquisition/fetch_error")
            record_blocked(target, failure.request.url, reason=repr(failure.value), run_id=self.run_id)

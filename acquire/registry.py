"""SourceRegistry: loads registry/*_sources.yaml -> scrapy.Request objects.

A source is DATA, not code (PROMPTS.md P2A). Nothing in this module or in
acquire/spiders/sources.py hardcodes a URL, an institution ID or a year --
everything below is a YAML edit away from a new institution, a new year or a
pasted one-off link. There are two entry types, sharing this one build path:

  type: pattern     templated URL(s) resolved from `enumerator.years`, OR a
                     discovery URL (e.g. a WordPress media-search endpoint)
                     resolved from `enumerator.matches` and filtered after
                     the fact against that response's own JSON.
  type: adhoc_url    a single pasted URL, no template, no enumerator.
"""
from __future__ import annotations

import dataclasses
import glob
from dataclasses import dataclass, field
from typing import Any, Iterator

import scrapy
import yaml


@dataclass(frozen=True)
class FetchTarget:
    """One concrete thing to fetch, plus every provenance field that has to
    travel with it into the manifest (P-6, P-9). `url` is set for a direct
    fetch; `discovery_url` is set instead for a two-step (search, then
    follow) fetch, and is resolved to per-year `url`s by
    SourceSpider.parse_discovery once the search response is in hand.
    """

    source_id: str
    country: str
    institution_code: str
    institution_name: str
    entry_type: str  # "pattern" | "adhoc_url"
    expected_content_type: str | None
    period_type: str | None
    period_value: str | None
    robots_checked_at: str | None
    terms_reviewed_at: str | None
    url: str | None = None
    discovery_url: str | None = None
    discovery_matches: tuple[dict, ...] = field(default_factory=tuple)


def resolved_for_year(target: FetchTarget, year: Any, url: str) -> FetchTarget:
    """A discovery target, once its search response has named the real URL
    for one enumerated year."""
    return dataclasses.replace(
        target, url=url, period_value=str(year), discovery_url=None, discovery_matches=()
    )


class SourceRegistry:
    def __init__(self, targets: list[FetchTarget]):
        self.targets = targets

    @classmethod
    def from_yaml_glob(cls, pattern: str = "registry/*_sources.yaml") -> "SourceRegistry":
        targets: list[FetchTarget] = []
        paths = sorted(glob.glob(pattern))
        if not paths:
            raise FileNotFoundError(f"no registry files matched {pattern!r}")
        for path in paths:
            with open(path, encoding="utf-8") as f:
                doc = yaml.safe_load(f)
            targets.extend(cls._targets_from_doc(doc, path))
        return cls(targets)

    @staticmethod
    def _targets_from_doc(doc: dict[str, Any], path: str) -> Iterator[FetchTarget]:
        country = doc["country"]
        patterns = doc.get("verified_retrieval", {})

        for src in doc.get("sources", []):
            common = dict(
                source_id=src["source_id"],
                country=country,
                institution_code=src["institution_code"],
                institution_name=src["institution_name"],
                entry_type=src["type"],
                expected_content_type=src.get("expected_content_type"),
                period_type=src.get("period_type"),
                robots_checked_at=src.get("robots_checked_at"),
                terms_reviewed_at=src.get("terms_reviewed_at"),
            )

            if src["type"] == "adhoc_url":
                yield FetchTarget(**common, url=src["url"], period_value=src.get("period_value"))
                continue

            if src["type"] != "pattern":
                raise ValueError(f"{path}: {src['source_id']}: unknown source type {src['type']!r}")

            template = patterns[src["pattern"]]
            params = src.get("params", {})
            enumerator = src.get("enumerator", {})

            if "matches" in enumerator:
                # Discovery pattern: one search request now, real fetches
                # resolved later against the search response (see
                # SourceSpider.parse_discovery).
                search_url = template.format(**params)
                yield FetchTarget(
                    **common,
                    discovery_url=search_url,
                    discovery_matches=tuple(enumerator["matches"]),
                    period_value=None,
                )
            elif "years" in enumerator:
                for year in enumerator["years"]:
                    url = template.format(year=year, **params)
                    yield FetchTarget(**common, url=url, period_value=str(year))
            else:
                raise ValueError(
                    f"{path}: {src['source_id']}: pattern entry needs "
                    "enumerator.years or enumerator.matches"
                )

    def build_requests(self, spider) -> Iterator[scrapy.Request]:
        for target in self.targets:
            if target.discovery_url:
                yield scrapy.Request(
                    target.discovery_url,
                    callback=spider.parse_discovery,
                    errback=spider.on_request_error,
                    meta={"target": target},
                )
            else:
                yield scrapy.Request(
                    target.url,
                    callback=spider.save_raw,
                    errback=spider.on_request_error,
                    meta={"target": target},
                )

"""ManifestPipeline: writes provenance BEFORE anything touches bytes
(PROMPTS.md P2A).

The ordering inside process_item is load-bearing, not stylistic: the
manifest row is appended and flushed to disk first; the raw file is written
second, and only if there is a body and it isn't already on disk (P-4). A
crash between those two steps leaves a manifest run-entry pointing at a raw
file that doesn't exist yet -- which is exactly the condition
scripts/run_acquire.py's self-verification (P-10) scans for, rather than the
pipeline silently hiding a partial write behind a would-be atomic step that
covers both.
"""
from __future__ import annotations

from acquire.manifestlog import append_run
from acquire.storage import raw_path, sha256_of, write_once


class ManifestPipeline:
    def process_item(self, item, spider):
        target = item["target"]
        body = item["body"]

        if item["http_status"] == 304:
            sha256 = item.get("prior_sha256")
            if sha256 is None:
                spider.logger.error(
                    "304 Not Modified with no known prior sha256 for %s -- "
                    "cannot attribute this response to any content, dropping",
                    item["url"],
                )
                spider.crawler.stats.inc_value("acquisition/304_without_prior")
                return item
        else:
            sha256 = sha256_of(body)

        robots_obeyed = spider.settings.getbool("ROBOTSTXT_OBEY")
        run_entry = {
            "run_id": item["run_id"],
            "url": item["url"],
            "http_status": item["http_status"],
            "etag": item["etag"],
            "last_modified": item["last_modified"],
            "content_type": item["content_type"],
            "fetched_at": item["fetched_at"],
            "source": "scrapy",
            # Provenance for the 2026-09-14 ROBOTSTXT_OBEY=False decision
            # (CLAUDE.md "Recorded decisions", gate/P2A-acquire.md) -- every
            # run entry states plainly whether this fetch happened under the
            # global override, not just the institutions it was added for.
            "robots_override": "global" if not robots_obeyed else None,
            "override_reason": "see gate/P2A-acquire.md" if not robots_obeyed else None,
        }

        # Manifest first (P2A: "writes provenance BEFORE anything touches bytes").
        append_run(
            sha256=sha256,
            source_id=target.source_id,
            institution_code=target.institution_code,
            institution_name=target.institution_name,
            country=target.country,
            canonical_url=item["url"],
            period_type=target.period_type,
            period_value=target.period_value,
            run_entry=run_entry,
        )

        # Raw bytes second.
        if body is not None:
            path = raw_path(sha256, item["content_type"])
            created = write_once(path, body)
            spider.crawler.stats.inc_value(
                "acquisition/raw_file_created" if created else "acquisition/raw_file_already_present"
            )

        item["sha256"] = sha256
        return item

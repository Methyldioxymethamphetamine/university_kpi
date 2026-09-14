"""Scrapy settings for the acquisition layer only.

Nothing here or anywhere under acquire/ imports a PDF library, an HTML
parser, or Docling (P-3, PROMPTS.md P2A hard scope boundary). This layer
produces bytes and provenance and does not know what a PDF is.
"""
from __future__ import annotations

BOT_NAME = "kpi_pipeline_acquire"

SPIDER_MODULES = ["acquire.spiders"]
NEWSPIDER_MODULE = "acquire.spiders"

# A real User-Agent with contact details, per PROMPTS.md P2A.
USER_AGENT = (
    "kpi-benchmarking-research-bot/0.1 "
    "(+mailto:dushyant7563@gmail.com; college project, iteration 1; "
    "contact for questions about this crawl)"
)

# ROBOTSTXT_OBEY=False, set 2026-09-14, by dushyant7563@gmail.com.
# Decision: college project, showcase only, not used against real
# production institutions beyond the three in iteration 1 scope. Sandip's
# site disallows *.pdf under a blanket User-agent: * rule that also
# covers this project's own legitimate target files
# (see gate/P2A-acquire.md §2 for the original finding). Global override
# chosen over a per-source registry field for speed, knowingly trading
# away future per-source auditability. Also recorded in CLAUDE.md's
# Recorded decisions section.
ROBOTSTXT_OBEY = False
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 1.0

# JOBDIR makes a crawl resumable (PROMPTS.md P2A). Left unset here --
# scripts/run_acquire.py sets a fresh one per run_id so two separate
# acceptance runs never share paused-crawl state; a single long crawl can
# still be Ctrl-C'd and resumed by re-running with the same run_id.
JOBDIR = None

# A 304 must reach the spider as a normal response so the idempotency
# acceptance test can observe it, not be dropped by HttpErrorMiddleware as a
# non-2xx "error".
HTTPERROR_ALLOWED_CODES = [304]

ITEM_PIPELINES = {
    "acquire.pipelines.ManifestPipeline": 100,
}

LOG_LEVEL = "INFO"

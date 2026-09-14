"""P1 CHECK A — idempotent, content-addressed acquisition via Scrapy.

Fetches the target URL, stores the body under spike/raw/sha256/<hash>,
and reports whether the fetch created a new file or found one already
present (content-addressed idempotency). Run twice to prove it.
"""
import hashlib
import json
import sys
from pathlib import Path

import scrapy
from scrapy.crawler import CrawlerProcess

URL = "https://www.nirfindia.org/nirfpdfcdn/2025/pdf/Overall/IR-O-U-0306.pdf"
STORE = Path(__file__).parent / "raw" / "sha256"
RESULT_PATH = Path(__file__).parent / "check_a_result.json"


class OneShotSpider(scrapy.Spider):
    name = "spike_one_shot"
    start_urls = [URL]
    custom_settings = {
        "ROBOTSTXT_OBEY": False,  # verified separately: no robots.txt exists (404)
        "LOG_LEVEL": "ERROR",
        "USER_AGENT": "kpi-pipeline-spike/0.1 (college project; one-time P1 test)",
    }

    def parse(self, response):
        body = response.body
        sha = hashlib.sha256(body).hexdigest()
        dest = STORE / sha
        existed_before = dest.exists()
        if not existed_before:
            dest.write_bytes(body)
        result = {
            "url": response.url,
            "status": response.status,
            "content_type": response.headers.get("Content-Type", b"").decode(),
            "bytes": len(body),
            "sha256": sha,
            "dest": str(dest),
            "file_existed_before_this_fetch": existed_before,
            "new_file_created": not existed_before,
        }
        RESULT_PATH.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    process = CrawlerProcess()
    process.crawl(OneShotSpider)
    process.start()

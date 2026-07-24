import html
import re

import httpx

from . import Posting

TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str) -> str:
    return html.unescape(TAG_RE.sub(" ", html.unescape(raw or ""))).strip()


def fetch(slug: str) -> list[Posting]:
    resp = httpx.get(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        params={"content": "true"},
        timeout=30,
    )
    resp.raise_for_status()
    postings = []
    for job in resp.json().get("jobs", []):
        location = (job.get("location") or {}).get("name", "") or ""
        postings.append(
            Posting(
                source="greenhouse",
                company=slug,
                title=job.get("title", ""),
                location=location,
                remote="remote" in location.lower(),
                url=job.get("absolute_url", ""),
                description=_strip_html(job.get("content", "")),
                posted_at=(job.get("first_published") or job.get("updated_at") or "")[:10],
            )
        )
    return postings

import html
import re

import httpx

from . import Posting

TAG_RE = re.compile(r"<[^>]+>")


def fetch(slug: str) -> list[Posting]:
    resp = httpx.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
        params={"includeCompensation": "true"},
        timeout=30,
    )
    resp.raise_for_status()
    postings = []
    for job in resp.json().get("jobs", []):
        if not job.get("isListed", True):
            continue
        description = job.get("descriptionPlain") or html.unescape(
            TAG_RE.sub(" ", job.get("descriptionHtml") or "")
        )
        postings.append(
            Posting(
                source="ashby",
                company=slug,
                title=job.get("title", ""),
                location=job.get("location", "") or "",
                remote=bool(job.get("isRemote")),
                url=job.get("jobUrl") or job.get("applyUrl") or "",
                description=description.strip(),
                posted_at=(job.get("publishedAt") or "")[:10],
            )
        )
    return postings

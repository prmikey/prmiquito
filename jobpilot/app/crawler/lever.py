from datetime import datetime, timezone

import httpx

from . import Posting


def fetch(slug: str) -> list[Posting]:
    resp = httpx.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, timeout=30)
    resp.raise_for_status()
    postings = []
    for job in resp.json():
        categories = job.get("categories") or {}
        location = categories.get("location", "") or ""
        workplace = (job.get("workplaceType") or "").lower()
        created_ms = job.get("createdAt")
        posted = (
            datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).date().isoformat()
            if created_ms
            else ""
        )
        postings.append(
            Posting(
                source="lever",
                company=slug,
                title=job.get("text", ""),
                location=location,
                remote=workplace == "remote" or "remote" in location.lower(),
                url=job.get("hostedUrl", ""),
                description=(job.get("descriptionPlain") or "").strip(),
                posted_at=posted,
            )
        )
    return postings

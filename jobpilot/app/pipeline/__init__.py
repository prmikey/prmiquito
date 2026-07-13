import hashlib
import logging
import threading
from datetime import date, datetime, timedelta

from .. import llm
from ..crawler import ashby, greenhouse, lever
from ..db import (
    STRICTNESS_THRESHOLDS,
    get_answers_bank,
    get_companies,
    get_db,
    get_profile,
    get_setting,
)
from . import drafting, matching

log = logging.getLogger("jobpilot.pipeline")

FETCHERS = {"greenhouse": greenhouse.fetch, "lever": lever.fetch, "ashby": ashby.fetch}

_run_lock = threading.Lock()


def _csv(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _dedupe_hash(company: str, title: str, location: str) -> str:
    key = f"{company}|{title}|{location}".lower()
    return hashlib.sha256(key.encode()).hexdigest()


def _passes_filters(posting, title_keywords, blocklist, remote_only, max_age_days) -> bool:
    title = posting.title.lower()
    haystack = f"{title} {posting.location.lower()}"
    if title_keywords and not any(kw in title for kw in title_keywords):
        return False
    if any(kw in haystack for kw in blocklist):
        return False
    if remote_only and not posting.remote:
        return False
    if posting.posted_at:
        try:
            posted = date.fromisoformat(posting.posted_at)
            if posted < date.today() - timedelta(days=max_age_days):
                return False
        except ValueError:
            pass
    return True


def discover(db) -> dict:
    """Fetch postings from all configured boards; insert new ones into the ledger."""
    title_keywords = _csv(get_setting(db, "title_keywords"))
    blocklist = _csv(get_setting(db, "blocklist"))
    remote_only = get_setting(db, "remote_only") == "1"
    max_age_days = int(get_setting(db, "max_age_days") or 30)

    stats = {"fetched": 0, "new": 0, "filtered": 0, "errors": []}
    for source, slugs in get_companies(db).items():
        for slug in slugs:
            try:
                postings = FETCHERS[source](slug)
            except Exception as exc:
                stats["errors"].append(f"{source}/{slug}: {exc}")
                log.warning("crawl failed for %s/%s: %s", source, slug, exc)
                continue
            stats["fetched"] += len(postings)
            for posting in postings:
                if not posting.title or not posting.url:
                    continue
                status = "discovered"
                if not _passes_filters(posting, title_keywords, blocklist, remote_only, max_age_days):
                    status = "filtered"
                cursor = db.execute(
                    "INSERT OR IGNORE INTO jobs (source, company, title, location, remote,"
                    " url, description, posted_at, dedupe_hash, status)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        posting.source,
                        posting.company,
                        posting.title,
                        posting.location,
                        int(posting.remote),
                        posting.url,
                        posting.description,
                        posting.posted_at,
                        _dedupe_hash(posting.company, posting.title, posting.location),
                        status,
                    ),
                )
                if cursor.rowcount:
                    stats["new" if status == "discovered" else "filtered"] += 1
    return stats


def match_and_draft(db) -> dict:
    """Score 'discovered' jobs, then draft materials for matches under the daily cap."""
    stats = {"scored": 0, "matched": 0, "skipped": 0, "queued": 0, "errors": []}
    profile = get_profile(db)
    if not profile["resume_json"]:
        stats["errors"].append("no parsed profile yet — add your resume on the Profile page")
        return stats

    threshold = STRICTNESS_THRESHOLDS.get(get_setting(db, "strictness"), 65)
    daily_cap = int(get_setting(db, "daily_cap") or 20)
    queued_today = db.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('queued','applied','interviewing','offer')"
        " AND date(updated_at) = date('now')"
    ).fetchone()[0]

    for job in db.execute("SELECT * FROM jobs WHERE status='discovered' ORDER BY id").fetchall():
        try:
            score, reason = matching.score_job(profile["resume_json"], job["title"], job["description"])
        except llm.LLMError as exc:
            stats["errors"].append(f"scoring job {job['id']}: {exc}")
            continue
        stats["scored"] += 1
        status = "matched" if score >= threshold else "skipped"
        stats["matched" if status == "matched" else "skipped"] += 1
        db.execute(
            "UPDATE jobs SET score=?, score_reason=?, status=?, updated_at=datetime('now') WHERE id=?",
            (score, reason, status, job["id"]),
        )
        db.commit()

    bank = get_answers_bank(db)
    for job in db.execute(
        "SELECT * FROM jobs WHERE status='matched' ORDER BY score DESC"
    ).fetchall():
        if queued_today >= daily_cap:
            break
        try:
            cover = drafting.draft_cover_letter(
                profile["resume_json"], job["company"], job["title"], job["description"]
            )
            answers = drafting.draft_answers(
                profile["resume_json"], bank, job["company"], job["title"], job["description"]
            )
        except llm.LLMError as exc:
            stats["errors"].append(f"drafting job {job['id']}: {exc}")
            continue
        db.execute(
            "INSERT INTO drafts (job_id, cover_letter, answers_json) VALUES (?,?,?)"
            " ON CONFLICT(job_id) DO UPDATE SET cover_letter=excluded.cover_letter,"
            " answers_json=excluded.answers_json, updated_at=datetime('now')",
            (job["id"], cover, answers),
        )
        db.execute(
            "UPDATE jobs SET status='queued', updated_at=datetime('now') WHERE id=?",
            (job["id"],),
        )
        db.commit()
        queued_today += 1
        stats["queued"] += 1
    return stats


def run_pipeline() -> str:
    """Full cycle: discover -> match -> draft. Serialized; safe to call from
    the scheduler and the dashboard button concurrently."""
    if not _run_lock.acquire(blocking=False):
        return "pipeline already running"
    try:
        with get_db() as db:
            d = discover(db)
            m = match_and_draft(db)
            errors = d["errors"] + m["errors"]
            summary = (
                f"fetched {d['fetched']}, new {d['new']}, scored {m['scored']}, "
                f"matched {m['matched']}, queued {m['queued']}"
                + (f", errors: {'; '.join(errors[:5])}" if errors else "")
            )
            db.execute("INSERT INTO pipeline_log (summary) VALUES (?)", (summary,))
            log.info("pipeline run at %s: %s", datetime.now().isoformat(), summary)
            return summary
    finally:
        _run_lock.release()

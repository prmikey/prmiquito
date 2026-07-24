import json
import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import llm, pipeline
from .config import APP_DIR, CRAWL_INTERVAL_HOURS
from .db import (
    KANBAN_STATUSES,
    get_answers_bank,
    get_companies,
    get_db,
    get_profile,
    get_setting,
    init_db,
    set_job_status,
    set_setting,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="JobPilot")
templates = Jinja2Templates(directory=APP_DIR / "templates")
scheduler = BackgroundScheduler()

PROFILE_PARSE_SYSTEM = (
    "Parse this resume into a JSON object with keys: name, email, phone, links "
    "(list), summary, skills (list), work_history (list of {company, title, "
    "start, end, highlights}), education (list of {school, degree, year}). "
    "Use only information present in the resume; leave fields empty rather "
    "than guessing. Return ONLY the JSON object."
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    scheduler.add_job(pipeline.run_pipeline, "interval", hours=CRAWL_INTERVAL_HOURS)
    scheduler.start()


@app.on_event("shutdown")
def shutdown() -> None:
    scheduler.shutdown(wait=False)


def render(request: Request, template: str, **ctx):
    return templates.TemplateResponse(request, template, ctx)


@app.get("/")
def jobs_page(request: Request, status: str = ""):
    with get_db() as db:
        where, params = "", []
        if status:
            where, params = "WHERE status=?", [status]
        jobs = db.execute(
            f"SELECT * FROM jobs {where} ORDER BY score IS NULL, score DESC, id DESC LIMIT 500",
            params,
        ).fetchall()
        counts = dict(
            db.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall()
        )
        last_run = db.execute(
            "SELECT * FROM pipeline_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return render(request, "jobs.html", jobs=jobs, counts=counts, active=status, last_run=last_run)


@app.post("/run")
def run_now():
    threading.Thread(target=pipeline.run_pipeline, daemon=True).start()
    return RedirectResponse("/", status_code=303)


@app.get("/review")
def review_page(request: Request):
    with get_db() as db:
        rows = db.execute(
            "SELECT jobs.*, drafts.cover_letter, drafts.answers_json FROM jobs"
            " JOIN drafts ON drafts.job_id = jobs.id"
            " WHERE jobs.status='queued' ORDER BY jobs.score DESC"
        ).fetchall()
    queue = [
        {"job": row, "answers": json.loads(row["answers_json"] or "[]")} for row in rows
    ]
    return render(request, "review.html", queue=queue)


@app.post("/jobs/{job_id}/draft")
async def save_draft(job_id: int, request: Request):
    form = await request.form()
    answers = []
    index = 0
    while f"q{index}" in form:
        answers.append(
            {
                "question": form[f"q{index}"],
                "answer": form.get(f"a{index}", ""),
                "source": "edited" if form.get(f"a{index}", "") else "blank",
            }
        )
        index += 1
    with get_db() as db:
        db.execute(
            "UPDATE drafts SET cover_letter=?, answers_json=?, updated_at=datetime('now')"
            " WHERE job_id=?",
            (form.get("cover_letter", ""), json.dumps(answers), job_id),
        )
    return RedirectResponse("/review", status_code=303)


@app.post("/jobs/{job_id}/status")
def change_status(job_id: int, status: str = Form(...), back: str = Form("/")):
    allowed = set(KANBAN_STATUSES) | {"skipped"}
    with get_db() as db:
        if status in allowed:
            set_job_status(db, job_id, status)
    return RedirectResponse(back, status_code=303)


@app.get("/board")
def board_page(request: Request):
    with get_db() as db:
        columns = {
            status: db.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY updated_at DESC", (status,)
            ).fetchall()
            for status in KANBAN_STATUSES
        }
    return render(request, "board.html", columns=columns, statuses=KANBAN_STATUSES)


@app.get("/profile")
def profile_page(request: Request, error: str = ""):
    with get_db() as db:
        profile = get_profile(db)
        bank = get_answers_bank(db)
    return render(request, "profile.html", profile=profile, bank=bank, error=error)


@app.post("/profile/resume")
def save_resume(resume_text: str = Form("")):
    with get_db() as db:
        db.execute(
            "UPDATE profile SET resume_text=?, updated_at=datetime('now') WHERE id=1",
            (resume_text,),
        )
    return RedirectResponse("/profile", status_code=303)


@app.post("/profile/parse")
def parse_resume():
    with get_db() as db:
        profile = get_profile(db)
        if not profile["resume_text"].strip():
            return RedirectResponse("/profile?error=paste+your+resume+first", status_code=303)
        try:
            parsed = llm.chat_json(PROFILE_PARSE_SYSTEM, profile["resume_text"][:12000])
        except llm.LLMError as exc:
            return RedirectResponse(f"/profile?error={str(exc)[:200]}", status_code=303)
        db.execute(
            "UPDATE profile SET resume_json=?, updated_at=datetime('now') WHERE id=1",
            (json.dumps(parsed, indent=2),),
        )
    return RedirectResponse("/profile", status_code=303)


@app.post("/profile/answers")
async def save_answers(request: Request):
    form = await request.form()
    with get_db() as db:
        index = 0
        while f"q{index}" in form:
            question = form[f"q{index}"].strip()
            if question:
                db.execute(
                    "INSERT INTO answers_bank (question, answer) VALUES (?,?)"
                    " ON CONFLICT(question) DO UPDATE SET answer=excluded.answer",
                    (question, form.get(f"a{index}", "")),
                )
            index += 1
        new_q = form.get("new_question", "").strip()
        if new_q:
            db.execute(
                "INSERT INTO answers_bank (question, answer) VALUES (?,?)"
                " ON CONFLICT(question) DO UPDATE SET answer=excluded.answer",
                (new_q, form.get("new_answer", "")),
            )
    return RedirectResponse("/profile", status_code=303)


@app.get("/settings")
def settings_page(request: Request, error: str = ""):
    with get_db() as db:
        settings = {
            key: get_setting(db, key)
            for key in (
                "title_keywords",
                "blocklist",
                "remote_only",
                "strictness",
                "daily_cap",
                "max_age_days",
            )
        }
        companies = get_companies(db)
    return render(
        request,
        "settings.html",
        settings=settings,
        companies_json=json.dumps(companies, indent=2),
        error=error,
    )


@app.post("/settings")
def save_settings(
    title_keywords: str = Form(""),
    blocklist: str = Form(""),
    remote_only: str = Form("0"),
    strictness: str = Form("balanced"),
    daily_cap: str = Form("20"),
    max_age_days: str = Form("30"),
    companies_json: str = Form("{}"),
):
    try:
        companies = json.loads(companies_json)
        assert isinstance(companies, dict)
    except (json.JSONDecodeError, AssertionError):
        return RedirectResponse("/settings?error=companies+must+be+a+JSON+object", status_code=303)
    with get_db() as db:
        set_setting(db, "title_keywords", title_keywords)
        set_setting(db, "blocklist", blocklist)
        set_setting(db, "remote_only", "1" if remote_only == "1" else "0")
        set_setting(db, "strictness", strictness if strictness in ("strict", "balanced", "loose") else "balanced")
        set_setting(db, "daily_cap", str(max(1, int(daily_cap or 20))))
        set_setting(db, "max_age_days", str(max(1, int(max_age_days or 30))))
        set_setting(db, "companies", json.dumps(companies))
    return RedirectResponse("/settings", status_code=303)

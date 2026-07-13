# JobPilot

Self-hosted job-application copilot: crawls company career pages (Greenhouse,
Lever, Ashby JSON APIs), scores each posting against your resume with an LLM,
drafts a tailored cover letter and screening answers for the matches, and puts
everything in a review queue + kanban tracker. **Nothing is ever submitted
automatically** — you review, copy-paste, and click apply yourself.

The LLM is any OpenAI-compatible endpoint. Default config assumes Ollama
running on the same machine (e.g. a Hermes model: `ollama pull hermes3`), but
you can point it at any hosted API instead.

## Quick start (Docker, on your VM)

```bash
cd jobpilot
cp config.example.env .env        # edit if your LLM isn't local Ollama
docker compose up -d --build
# open http://<vm>:8300
```

Or without Docker:

```bash
pip install -r requirements.txt
cp config.example.env .env
uvicorn app.main:app --host 0.0.0.0 --port 8300
```

The dashboard binds to all interfaces and has **no authentication** — keep it
on a private network / behind a VPN or reverse-proxy auth.

## Using it

1. **Profile** — paste your resume as text, click *Parse with LLM*. Fill in the
   screening answers bank (notice period, salary, work auth, …). These are
   reused on every application; blanks get flagged per-job instead of guessed.
2. **Settings** — set title keywords, blocklist, remote-only, strictness
   (strict ≥80 / balanced ≥65 / loose ≥50 fit score), daily cap, and the
   company boards to crawl. Slugs come from career-page URLs:
   `boards.greenhouse.io/<slug>`, `jobs.lever.co/<slug>`,
   `jobs.ashbyhq.com/<slug>`.
3. **Jobs** — *Run discovery now* (also runs automatically every
   `CRAWL_INTERVAL_HOURS`). New postings are deduped against a permanent
   ledger, filtered, scored, and matches get drafts — capped per day.
4. **Review queue** — edit the cover letter and answers (AI-drafted and blank
   answers are flagged), open the posting, submit manually, *Mark applied*.
5. **Board** — track applied → interviewing → offer/rejected.

## Design notes

- Deterministic pipeline (crawl/dedupe/filter/track) is plain code; the LLM is
  only called for three stateless jobs: resume parsing, fit scoring, drafting.
- Dedupe hash is `company|title|location` — a job is applied to once, ever.
- Drafting prompts are grounded strictly in your parsed profile and instructed
  never to invent credentials; anything the model composed itself is flagged
  in the review queue.
- Data lives in one SQLite file (`data/jobpilot.db`); back that up and you've
  backed up everything.

## Not included (yet)

Browser auto-submit (Playwright), email inbox parsing for
rejections/interviews, and per-job form-question scraping are deliberate
later milestones — see the plan in the repo history.

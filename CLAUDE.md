# Lead Sourcer (Local)

A small, single-user, local web app for searching and tracking sales/outreach
leads at target companies. It's a personal, from-scratch reimplementation of
the *idea* behind a club tool (ABA Sourcing) whose hosted backend is
currently broken — this is not a clone of that app's code, just similar
functionality for one person, run entirely on localhost.

## Why this exists

The club's hosted version (abasourcing.com) has a backend bug where every
search returns zero results regardless of the company queried — likely a
dead/expired integration with its people-search data provider. Club exec
can't fix it right now. This is a minimal personal substitute: same basic
workflow (search a company, get leads, save the ones you want), but backed
by a data provider *you* configure with your own API key, so it's not
dependent on the club's infrastructure.

## Explicit non-goals

- No multi-user accounts, teams, or login system — single user, local only.
- No deployment/hosting concerns — runs via one local command.
- Do NOT try to reverse-engineer or replicate abasourcing.com's actual
  backend code or infrastructure. This is an original, independent
  implementation of similar functionality.
- No scraping of LinkedIn or any site's HTML directly — use a real,
  ToS-compliant people-search API provider (see below).

## Tech stack (keep it simple)

- **Backend:** Python + FastAPI
- **DB:** SQLite, single file (`data.db`), plain `sqlite3` or SQLAlchemy —
  whichever is less boilerplate
- **Frontend:** server-rendered Jinja2 templates + minimal vanilla JS (no
  build step, no separate frontend framework). Plain CSS is fine.
- **Run command:** `uvicorn app:app --reload`, opened at `http://localhost:8000`
- **Secrets:** a local `.env` file (gitignored), loaded with `python-dotenv`.
  Never commit or hardcode API keys.

## Data provider integration

Default to **Apollo.io's People Search API**
(`POST https://api.apollo.io/v1/mixed_people/search`) — its parameters map
cleanly onto the fields below (organization domain, person titles, person
locations, person seniorities, per-page count). The user will supply their
own Apollo API key.

Build the provider call behind a small adapter (e.g. `providers/apollo.py`
exposing a single `search(domain, job_titles, locations, seniority,
max_results) -> list[Lead]` function) so a different provider (Hunter.io,
PeopleDataLabs, Proxycurl, etc.) could be swapped in later without touching
routes, templates, or the DB layer.

Read the key from `APOLLO_API_KEY` in `.env`. Ship a `.env.example` with a
placeholder, not a real key.

**Critical requirement, directly motivated by the bug we're working around:**
if the provider call fails, returns a non-200 status, or the key is
missing/invalid, the UI must show a real, visible error message — never
silently render an empty results list. Silently-empty results with no error
is exactly the unfixed bug in the original app; don't reproduce it here.

## Core features

1. **Search Leads** (`/`) — form with:
   - Company Domain / Name (text)
   - Max Results (number, default 25)
   - Job Titles (comma-separated)
   - Locations (comma-separated)
   - Seniority (multi-select chips: Senior, Manager, Director, Head, VP,
     C-Level, Partner, Owner)

   Submitting calls the provider adapter server-side (API key never touches
   the browser) and renders results as a table: name, title, company,
   location, LinkedIn URL if available, email if available.

2. **Basket** (`/basket`) — save leads from search results into a persistent
   SQLite-backed list; view and remove saved leads.

3. **Settings** (`/settings`) — view whether an API key is currently
   configured (masked, e.g. `sk-...ab12`) and instructions for setting it in
   `.env`. Don't build in-app key editing that writes to `.env` unless it's
   trivial — a readme instruction is fine too.

Skip the original app's "Team Leads" page entirely — it's a multi-user
feature that doesn't apply here.

## Data model (SQLite)

- `leads`: id, name, title, company, domain, location, seniority,
  linkedin_url, email (nullable), source_provider, created_at
- `basket`: id, lead_id (FK → leads), added_at

Search results themselves don't need to be persisted until a user adds one
to the basket.

## Setup steps for Claude Code

1. Scaffold the FastAPI project: `app.py`, `providers/apollo.py`, `db.py`,
   `templates/`, `static/`, `requirements.txt`, `.env.example`, `.gitignore`
   (must include `.env` and `data.db`).
2. Implement the DB layer (create tables on startup if missing).
3. Implement the Apollo adapter per above, with clear error propagation.
4. Implement routes: `GET /`, `POST /search`, `POST /basket/add`,
   `GET /basket`, `POST /basket/remove`, `GET /settings`.
5. Minimal, clean templates — doesn't need to be fancy, just usable.
6. Write a short `README.md`: `pip install -r requirements.txt`,
   `cp .env.example .env` + add your Apollo key, then
   `uvicorn app:app --reload`.
7. Sanity-check locally: confirm a missing/invalid key surfaces a visible
   error (not an empty list), and that a valid key returns real results.

## Notes for whoever (Claude Code) builds this

- The user does not yet have an Apollo.io account/API key — they'll need to
  sign up separately and get their own before search actually returns data.
  The app should run and show a clear "no API key configured" state before
  that point, rather than crashing.
- This file was written by Claude (chat) after debugging the club's hosted
  tool with the user; it does not include any of that tool's credentials or
  source code, intentionally.

import os
import re
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
from providers.apollo import ProviderError, search as apollo_search

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SENIORITY_OPTIONS = [
    "Senior",
    "Manager",
    "Director",
    "Head",
    "VP",
    "C-Level",
    "Partner",
    "Owner",
]


@app.on_event("startup")
def on_startup():
    db.init_db()


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _parse_exclusion_paste(text: str) -> list[dict]:
    """Parse pasted rows (e.g. copied from a Team Leads table) into
    {name, email, company} dicts. Tolerant of tab- or comma-separated
    lines with extra columns (title, added-by, status, etc.) mixed in."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        email_match = EMAIL_RE.search(line)
        email = email_match.group(0) if email_match else None
        remainder = line.replace(email, "") if email else line
        parts = [p.strip(" \t,") for p in re.split(r"\t|,", remainder) if p.strip(" \t,")]
        name = parts[0] if parts else None
        company = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 else None)
        if not name and not email:
            continue
        entries.append({"name": name, "email": email, "company": company})
    return entries


def _mark_excluded(results: list[dict], emails: set[str], names: set[str]) -> None:
    for lead in results:
        email = (lead.get("email") or "").strip().lower()
        name = (lead.get("name") or "").strip().lower()
        lead["excluded"] = bool((email and email in emails) or (name and name in names))


def _build_tsv(results: list[dict]) -> str:
    header = ["First Name", "Last Name", "Position", "Company", "Email"]
    lines = ["\t".join(header)]
    for lead in results:
        row = [
            lead.get("first_name") or "",
            lead.get("last_name") or "",
            lead.get("title") or "",
            lead.get("company") or "",
            lead.get("email") or "",
        ]
        lines.append("\t".join(row))
    return "\n".join(lines)


@app.get("/")
def index(request: Request, blocked: str | None = None):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "seniority_options": SENIORITY_OPTIONS,
            "results": None,
            "tsv": None,
            "error": None,
            "blocked": blocked,
            "form": {},
        },
    )


@app.post("/search")
def do_search(
    request: Request,
    domain: str = Form(...),
    max_results: int = Form(25),
    job_titles: str = Form(""),
    locations: str = Form(""),
    seniority: list[str] = Form([]),
):
    form_values = {
        "domain": domain,
        "max_results": max_results,
        "job_titles": job_titles,
        "locations": locations,
        "seniority": seniority,
    }

    error = None
    results = []
    try:
        leads = apollo_search(
            domain=domain,
            job_titles=_split_csv(job_titles),
            locations=_split_csv(locations),
            seniority=seniority,
            max_results=max_results,
        )
        results = [
            {
                "name": lead.name,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "title": lead.title,
                "company": lead.company,
                "domain": domain,
                "location": lead.location,
                "seniority": ", ".join(seniority) if seniority else None,
                "linkedin_url": lead.linkedin_url,
                "email": lead.email,
            }
            for lead in leads
        ]
        with db.get_conn() as conn:
            emails, names = db.get_exclusion_sets(conn)
        _mark_excluded(results, emails, names)
    except ProviderError as exc:
        error = str(exc)

    tsv_rows = [lead for lead in results if not lead.get("excluded")]

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "seniority_options": SENIORITY_OPTIONS,
            "results": results,
            "tsv": _build_tsv(tsv_rows) if tsv_rows else None,
            "error": error,
            "blocked": None,
            "form": form_values,
        },
    )


@app.post("/basket/add")
def basket_add(
    name: str = Form(...),
    title: str = Form(""),
    company: str = Form(""),
    domain: str = Form(""),
    location: str = Form(""),
    seniority: str = Form(""),
    linkedin_url: str = Form(""),
    email: str = Form(""),
):
    lead = {
        "name": name,
        "title": title or None,
        "company": company or None,
        "domain": domain or None,
        "location": location or None,
        "seniority": seniority or None,
        "linkedin_url": linkedin_url or None,
        "email": email or None,
        "source_provider": "apollo",
    }
    with db.get_conn() as conn:
        emails, names = db.get_exclusion_sets(conn)
        email_key = (email or "").strip().lower()
        name_key = (name or "").strip().lower()
        if (email_key and email_key in emails) or (name_key and name_key in names):
            return RedirectResponse(url=f"/?blocked={quote(name)}", status_code=303)

        lead_id = db.find_lead_by_identity(conn, lead)
        if lead_id is None:
            lead_id = db.insert_lead(conn, lead)
        db.add_to_basket(conn, lead_id)

    return RedirectResponse(url="/", status_code=303)


@app.get("/basket")
def basket_view(request: Request):
    with db.get_conn() as conn:
        rows = db.list_basket(conn)
    return templates.TemplateResponse(
        request, "basket.html", {"leads": rows}
    )


@app.post("/basket/remove")
def basket_remove(basket_id: int = Form(...)):
    with db.get_conn() as conn:
        db.remove_from_basket(conn, basket_id)
    return RedirectResponse(url="/basket", status_code=303)


@app.get("/exclusions")
def exclusions_view(request: Request):
    with db.get_conn() as conn:
        rows = db.list_excluded_leads(conn)
    return templates.TemplateResponse(
        request, "exclusions.html", {"excluded": rows}
    )


@app.post("/exclusions/import")
def exclusions_import(paste: str = Form(...)):
    entries = _parse_exclusion_paste(paste)
    with db.get_conn() as conn:
        db.add_excluded_leads(conn, entries)
    return RedirectResponse(url="/exclusions", status_code=303)


@app.post("/exclusions/remove")
def exclusions_remove(excluded_id: int = Form(...)):
    with db.get_conn() as conn:
        db.remove_excluded_lead(conn, excluded_id)
    return RedirectResponse(url="/exclusions", status_code=303)


@app.get("/settings")
def settings_view(request: Request):
    api_key = os.environ.get("APOLLO_API_KEY", "").strip()
    if api_key:
        masked = f"{api_key[:3]}...{api_key[-4:]}" if len(api_key) > 7 else "***"
        configured = True
    else:
        masked = None
        configured = False
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"configured": configured, "masked": masked},
    )

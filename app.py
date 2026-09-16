import os

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


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "seniority_options": SENIORITY_OPTIONS,
            "results": None,
            "error": None,
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
    except ProviderError as exc:
        error = str(exc)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "seniority_options": SENIORITY_OPTIONS,
            "results": results,
            "error": error,
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

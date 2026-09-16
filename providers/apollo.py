"""Apollo.io People Search adapter.

Exposes a single `search(...)` function returning a list of `Lead`.
Any failure (missing/invalid key, non-200 response, network error) raises
`ProviderError` with a human-readable message — callers must surface this
to the UI rather than swallowing it into an empty result list.
"""

import os
from dataclasses import dataclass
from typing import Optional

import requests

APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"


class ProviderError(Exception):
    """Raised when the provider call fails for any reason. Message is user-facing."""


@dataclass
class Lead:
    name: str
    first_name: Optional[str]
    last_name: Optional[str]
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    linkedin_url: Optional[str]
    email: Optional[str]


def _get_api_key() -> str:
    key = os.environ.get("APOLLO_API_KEY", "").strip()
    if not key:
        raise ProviderError(
            "No Apollo API key configured. Add APOLLO_API_KEY to your .env file "
            "(see Settings page for instructions)."
        )
    return key


def search(
    domain: str,
    job_titles: list[str],
    locations: list[str],
    seniority: list[str],
    max_results: int = 25,
) -> list[Lead]:
    api_key = _get_api_key()

    per_page = max(1, min(max_results, 100))
    payload = {
        "q_organization_domains": domain,
        "person_titles": job_titles,
        "person_locations": locations,
        "person_seniorities": [s.lower() for s in seniority],
        "per_page": per_page,
        "page": 1,
    }
    # Strip empty fields so Apollo doesn't over-filter on blanks.
    payload = {k: v for k, v in payload.items() if v not in (None, "", [])}

    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }

    try:
        resp = requests.post(APOLLO_SEARCH_URL, json=payload, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise ProviderError(f"Could not reach Apollo API: {exc}") from exc

    if resp.status_code == 401 or resp.status_code == 403:
        raise ProviderError(
            "Apollo API rejected the request — your API key appears to be "
            "invalid or unauthorized (HTTP %d)." % resp.status_code
        )
    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("error", resp.text[:200])
        except ValueError:
            detail = resp.text[:200]
        raise ProviderError(
            f"Apollo API returned an error (HTTP {resp.status_code}): {detail}"
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise ProviderError("Apollo API returned an unparseable response.") from exc

    people = data.get("people", [])
    leads: list[Lead] = []
    for person in people[:max_results]:
        org = person.get("organization") or {}
        name = person.get("name") or "Unknown"
        first_name = person.get("first_name")
        last_name = person.get("last_name")
        if not first_name and not last_name and name != "Unknown":
            parts = name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else None
        leads.append(
            Lead(
                name=name,
                first_name=first_name,
                last_name=last_name,
                title=person.get("title"),
                company=org.get("name") or person.get("organization_name"),
                location=person.get("city") or person.get("state") or person.get("country"),
                linkedin_url=person.get("linkedin_url"),
                email=person.get("email"),
            )
        )
    return leads

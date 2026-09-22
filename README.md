# Lead Sourcer (Local)

A small, single-user, local web app for searching and tracking sales/outreach
leads at target companies. See `CLAUDE.md` for background and design notes.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# then edit .env and set APOLLO_API_KEY=your_real_key
uvicorn app:app --reload
```

Open http://localhost:8000 in your browser.

## Usage

1. **Search** (`/`) — enter a company domain/name, optional job titles,
   locations, and seniority levels, then submit to query Apollo.io. Results
   render as a table you can add to your basket.
2. **Basket** (`/basket`) — view and remove leads you've saved.
3. **Settings** (`/settings`) — check whether an Apollo API key is currently
   configured (masked) and instructions for setting one.

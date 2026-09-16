import sqlite3
from contextlib import contextmanager

DB_PATH = "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    title TEXT,
    company TEXT,
    domain TEXT,
    location TEXT,
    seniority TEXT,
    linkedin_url TEXT,
    email TEXT,
    source_provider TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS basket (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS excluded_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    company TEXT,
    note TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def insert_lead(conn, lead: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO leads (name, title, company, domain, location, seniority,
                            linkedin_url, email, source_provider)
        VALUES (:name, :title, :company, :domain, :location, :seniority,
                :linkedin_url, :email, :source_provider)
        """,
        lead,
    )
    return cur.lastrowid


def find_lead_by_identity(conn, lead: dict):
    """Find an existing lead with the same identity to avoid duplicate rows."""
    row = conn.execute(
        """
        SELECT id FROM leads
        WHERE name = ? AND title IS ? AND company IS ? AND linkedin_url IS ?
        """,
        (lead["name"], lead["title"], lead["company"], lead["linkedin_url"]),
    ).fetchone()
    return row["id"] if row else None


def add_to_basket(conn, lead_id: int):
    existing = conn.execute(
        "SELECT id FROM basket WHERE lead_id = ?", (lead_id,)
    ).fetchone()
    if existing:
        return existing["id"]
    cur = conn.execute("INSERT INTO basket (lead_id) VALUES (?)", (lead_id,))
    return cur.lastrowid


def remove_from_basket(conn, basket_id: int):
    conn.execute("DELETE FROM basket WHERE id = ?", (basket_id,))


def list_basket(conn):
    return conn.execute(
        """
        SELECT basket.id AS basket_id, basket.added_at, leads.*
        FROM basket
        JOIN leads ON leads.id = basket.lead_id
        ORDER BY basket.added_at DESC
        """
    ).fetchall()


def get_lead(conn, lead_id: int):
    return conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()


def add_excluded_leads(conn, entries: list[dict]) -> int:
    """Insert excluded-lead entries, skipping ones that already exist by email
    (or by name when no email is given). Returns the number actually inserted."""
    inserted = 0
    for entry in entries:
        email = entry.get("email") or None
        name = entry.get("name") or None
        if email:
            existing = conn.execute(
                "SELECT id FROM excluded_leads WHERE email = ?", (email,)
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id FROM excluded_leads WHERE name = ? AND email IS NULL",
                (name,),
            ).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO excluded_leads (name, email, company, note) VALUES (?, ?, ?, ?)",
            (name, email, entry.get("company"), entry.get("note")),
        )
        inserted += 1
    return inserted


def list_excluded_leads(conn):
    return conn.execute(
        "SELECT * FROM excluded_leads ORDER BY added_at DESC"
    ).fetchall()


def remove_excluded_lead(conn, excluded_id: int):
    conn.execute("DELETE FROM excluded_leads WHERE id = ?", (excluded_id,))


def get_exclusion_sets(conn):
    """Returns (emails set, names set) of already-claimed leads, lowercased."""
    rows = conn.execute("SELECT name, email FROM excluded_leads").fetchall()
    emails = {row["email"].strip().lower() for row in rows if row["email"]}
    names = {row["name"].strip().lower() for row in rows if row["name"]}
    return emails, names

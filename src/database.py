"""
database.py
-----------
Everything related to STORING and QUERYING checkouts in a local SQLite
database. SQLite is a tiny database that lives in a single file on your
computer (checkouts.db) -- no server to install. Python has it built in.

WHY A DATABASE INSTEAD OF JUST WRITING TO EXCEL EACH TIME?
- You told me you want *different* exports depending on the filters you type.
- If we saved straight to Excel, every new filter would mean re-reading all
  of Discord again (slow, and limited by rate limits).
- Instead we save every checkout ONCE into the database. Then each /export
  is just a fast query against local data. Excel becomes a "view" of the DB.

KEY CONCEPT: the message_id is the PRIMARY KEY.
- Every Discord message has a unique ID. By using it as the primary key and
  "INSERT OR REPLACE", re-running the history backfill can't create duplicates
  -- the same checkout just overwrites its own identical row.
"""

import json
import sqlite3
from typing import Any, Optional

# The columns we store for each checkout. Keeping this list in one place
# means the table schema, the insert, and the export all stay in sync.
COLUMNS = [
    "message_id",      # Discord message ID (unique) -> primary key
    "created_at_iso",  # human-readable UTC timestamp of the message
    "created_ts",      # same moment as a number, for fast date-range filtering
    "product",         # the item, from the embed description line
    "module",
    "mode",
    "site",
    "size",
    "quantity",
    "total",           # the raw text, e.g. "$80.82"
    "total_amount",    # parsed number, e.g. 80.82, for summing spend
    "checkout_id",     # the "ID" field, e.g. 10-10451-115
    "delivery",
    "profile",
    "payment",
    "proxy_group",
    "order_number",    # the "Order #" field
    "order_url",
    "is_preorder",
    "raw_json",        # a JSON backup of every field, in case a new field appears
]


def connect() -> sqlite3.Connection:
    """Open (or create) the database file and return a connection."""
    conn = sqlite3.connect(DB_PATH)
    # row_factory lets us read rows as dict-like objects (row["profile"])
    # instead of by numeric position (row[10]). Much easier to read.
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the checkouts table if it doesn't already exist."""
    columns_sql = ",\n            ".join(
        # message_id is the PRIMARY KEY; total_amount/created_ts are numbers;
        # everything else is stored as text.
        f"{col} REAL" if col in ("total_amount", "created_ts")
        else f"{col} TEXT PRIMARY KEY" if col == "message_id"
        else f"{col} TEXT"
        for col in COLUMNS
    )
    with connect() as conn:
        conn.execute(f"CREATE TABLE IF NOT EXISTS checkouts (\n            {columns_sql}\n        )")


def upsert_checkout(record: dict[str, Any]) -> bool:
    """
    Insert a checkout, or replace it if we've already stored that message_id.
    Returns True if this was a brand-new row, False if it already existed.
    """
    # Figure out if the row already exists (so we can report "new" vs "seen").
    with connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM checkouts WHERE message_id = ?",
            (record["message_id"],),
        ).fetchone()

        # Build the INSERT dynamically from COLUMNS so we never mismatch.
        placeholders = ", ".join("?" for _ in COLUMNS)
        col_names = ", ".join(COLUMNS)
        values = [record.get(col) for col in COLUMNS]

        conn.execute(
            f"INSERT OR REPLACE INTO checkouts ({col_names}) VALUES ({placeholders})",
            values,
        )
    return existing is None


def _build_filters(
    profile: Optional[str] = None,
    site: Optional[str] = None,
    module: Optional[str] = None,
    date_from_ts: Optional[float] = None,
    date_to_ts: Optional[float] = None,
    contains: Optional[str] = None,
) -> tuple[str, list[Any]]:
    """
    Turn a set of optional filters into a SQL WHERE clause plus its values.
    We factor this out so BOTH query_checkouts (for /export) and the aggregate
    functions (for /stats) apply filters identically -- write it once, reuse it.

    IMPORTANT SAFETY NOTE: we use "?" placeholders and pass values separately
    instead of pasting them into the SQL string. This prevents SQL injection
    -- a classic bug where user input could otherwise alter the query itself.
    """
    clauses: list[str] = []
    params: list[Any] = []

    # "LIKE" with % wildcards = case-insensitive "contains" matching in SQLite.
    if profile:
        clauses.append("profile LIKE ?")
        params.append(f"%{profile}%")
    if site:
        clauses.append("site LIKE ?")
        params.append(f"%{site}%")
    if module:
        clauses.append("module LIKE ?")
        params.append(f"%{module}%")
    if date_from_ts is not None:
        clauses.append("created_ts >= ?")
        params.append(date_from_ts)
    if date_to_ts is not None:
        clauses.append("created_ts <= ?")
        params.append(date_to_ts)
    if contains:
        # Free-text search across the whole raw record.
        clauses.append("raw_json LIKE ?")
        params.append(f"%{contains}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def query_checkouts(**filters: Any) -> list[sqlite3.Row]:
    """Return the full checkout rows matching the given filters (for /export)."""
    where, params = _build_filters(**filters)
    sql = f"SELECT * FROM checkouts {where} ORDER BY created_ts ASC"
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def aggregate_totals(**filters: Any) -> dict[str, float]:
    """
    Return overall totals for the matching checkouts:
    {count, total_spend, avg_order_value}. Aggregation is done IN SQL with
    COUNT() and SUM() -- faster and cleaner than looping in Python.
    """
    where, params = _build_filters(**filters)
    sql = (
        "SELECT COUNT(*) AS count, "
        "COALESCE(SUM(total_amount), 0) AS total_spend "
        f"FROM checkouts {where}"
    )
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
    count = row["count"]
    spend = row["total_spend"]
    return {
        "count": count,
        "total_spend": spend,
        "avg_order_value": (spend / count) if count else 0.0,
    }


def group_by_column(column: str, limit: int = 10, **filters: Any) -> list[sqlite3.Row]:
    """
    Group matching checkouts by one column (e.g. 'profile' or 'site') and
    return each group's count and total spend, biggest first.

    NOTE: `column` is NOT user-typed free text -- it's chosen by our own code
    from a known list, so it's safe to place into the SQL. We still never put
    the *filter values* into SQL directly (those stay as ? params).
    """
    allowed = {"profile", "site", "module"}
    if column not in allowed:
        raise ValueError(f"Cannot group by '{column}'. Allowed: {allowed}")

    where, params = _build_filters(**filters)
    sql = (
        f"SELECT COALESCE({column}, '(none)') AS label, "
        "COUNT(*) AS count, "
        "COALESCE(SUM(total_amount), 0) AS spend "
        f"FROM checkouts {where} "
        f"GROUP BY {column} ORDER BY count DESC, spend DESC LIMIT ?"
    )
    with connect() as conn:
        return conn.execute(sql, [*params, limit]).fetchall()


# Imported here (not at the top) to keep the "what config do I need?" answer
# obvious, and to avoid a circular import if config ever grows.
from config import DB_PATH  # noqa: E402

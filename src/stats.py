"""
stats.py
--------
Computes summary statistics over the stored checkouts. This file has NO
Discord dependency on purpose -- it just crunches numbers from the database,
which keeps it easy to test. The /stats command in bot.py takes this data and
renders it into a Discord embed.

WHAT IT ANSWERS:
- How many checkouts? How much total spend? Average order value?
- Which profiles / sites are doing the most?
All of it respects the same filters as /export (profile, site, date range...).
"""

from typing import Any

import database


def compute_stats(top_n: int = 5, **filters: Any) -> dict[str, Any]:
    """
    Build a stats bundle for the checkouts matching `filters`.

    Returns a plain dict so it's easy to test and easy to render:
        {
          "count": int,
          "total_spend": float,
          "avg_order_value": float,
          "by_profile": [ {label, count, spend}, ... ],
          "by_site":    [ {label, count, spend}, ... ],
        }
    """
    totals = database.aggregate_totals(**filters)

    # GROUP BY profile, site, and channel, keeping only the top few of each.
    by_profile = database.group_by_column("profile", limit=top_n, **filters)
    by_site = database.group_by_column("site", limit=top_n, **filters)
    by_channel = database.group_by_column("channel_name", limit=top_n, **filters)

    def rows_to_dicts(rows: list) -> list[dict[str, Any]]:
        return [
            {"label": r["label"], "count": r["count"], "spend": round(r["spend"], 2)}
            for r in rows
        ]

    return {
        "count": totals["count"],
        "total_spend": round(totals["total_spend"], 2),
        "avg_order_value": round(totals["avg_order_value"], 2),
        "by_profile": rows_to_dicts(by_profile),
        "by_site": rows_to_dicts(by_site),
        "by_channel": rows_to_dicts(by_channel),
    }


def format_breakdown(rows: list[dict[str, Any]]) -> str:
    """
    Turn a breakdown list into a compact text block for a Discord embed field:
        MainProfile — 12 checkouts · $640.20
        BackupProfile — 3 checkouts · $180.00
    """
    if not rows:
        return "—"
    lines = [
        f"**{r['label']}** — {r['count']} checkouts · ${r['spend']:,.2f}"
        for r in rows
    ]
    return "\n".join(lines)

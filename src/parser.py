"""
parser.py
---------
Turns a Discord message (with its embed) into a plain dictionary that
matches our database columns.

KEY INSIGHT FROM YOUR SCREENSHOT:
The checkout data isn't messy free text -- it's a Discord "embed" made of
labeled "fields" (Module, Profile, Total, Order #, ...). Each field has a
.name ("Profile") and a .value ("Main"). So instead of guessing where data
is inside a blob of text, we can read it out cleanly by field name.
"""

import json
import re
from typing import Any, Optional

# Maps the field NAME shown in Discord  ->  our database column name.
# If HiddenAIO ever renames a field, this is the one place you'd update.
FIELD_MAP = {
    "Module": "module",
    "Mode": "mode",
    "Site": "site",
    "Size": "size",
    "Quantity": "quantity",
    "Total": "total",
    "ID": "checkout_id",
    "Delivery": "delivery",
    "Profile": "profile",
    "Payment": "payment",
    "Proxy Group": "proxy_group",
    "Order #": "order_number",
    "Order URL": "order_url",
    "Is Preorder": "is_preorder",
}


def _clean_value(text: Optional[str]) -> Optional[str]:
    """
    Tidy a raw field value from the embed.
    HiddenAIO wraps some values (like the profile name) in Discord "spoiler"
    markers -- a pair of vertical bars: ||Eugene 2 - 2765||. Those bars are just
    formatting to blur the text in chat; they aren't part of the real value, so
    we strip them (and any surrounding whitespace) for clean sheets and stats.
    """
    if text is None:
        return None
    cleaned = text.strip()
    if cleaned.startswith("||") and cleaned.endswith("||"):
        cleaned = cleaned[2:-2].strip()
    return cleaned


def _parse_money(text: Optional[str]) -> Optional[float]:
    """
    Pull a number out of a money string.
    "$80.82" -> 80.82   |   "26.94 USD" -> 26.94   |   None -> None
    """
    if not text:
        return None
    # Find the first thing that looks like 1234 or 1234.56 (commas removed).
    match = re.search(r"\d+\.?\d*", text.replace(",", ""))
    return float(match.group()) if match else None


def looks_like_checkout(embed: Any, keyword: str) -> bool:
    """
    Decide whether an embed is a successful-checkout card (vs some other
    webhook). We check whether the success keyword (e.g. "Checked Out")
    appears in the embed's author name, title, or description.
    """
    parts = [
        getattr(getattr(embed, "author", None), "name", "") or "",
        embed.title or "",
        embed.description or "",
    ]
    haystack = " ".join(parts).lower()
    return keyword.lower() in haystack


def parse_message(message: Any) -> Optional[dict[str, Any]]:
    """
    Convert a discord.Message into our record dict, or return None if the
    message doesn't contain a checkout embed we care about.

    `message` is a discord.py Message object. We read its .embeds list and
    its .created_at timestamp (which Discord provides in UTC).
    """
    if not message.embeds:
        return None

    embed = message.embeds[0]  # the checkout card is the first (only) embed

    # created_at is a timezone-aware datetime in UTC, straight from Discord.
    # We trust this over the text in the footer -- structured metadata beats
    # parsing a human-formatted date string.
    created_at = message.created_at

    # Which channel did this land in? getattr keeps it safe if a channel has no
    # name (e.g. a DM), and works with our fake test messages too.
    channel = getattr(message, "channel", None)

    record: dict[str, Any] = {
        "message_id": str(message.id),
        "created_at_iso": created_at.isoformat(),
        "created_ts": created_at.timestamp(),  # seconds since 1970, for filtering
        "channel_id": str(getattr(channel, "id", "")) or None,
        "channel_name": getattr(channel, "name", None),
        # The product line sits in the embed description, e.g.
        # "• 3x Pokemon TCG: 30th Celebration ... - 26.94 USD (OS)"
        "product": (embed.description or "").lstrip("• ").strip() or None,
    }

    # Walk every labeled field on the card and drop it into the right column.
    extra_fields: dict[str, str] = {}
    for field in embed.fields:
        value = _clean_value(field.value)  # strip spoiler bars / whitespace
        column = FIELD_MAP.get(field.name)
        if column:
            record[column] = value
        else:
            # Unknown/new field -> keep it in the JSON backup so nothing is lost.
            extra_fields[field.name] = value

    # Derived numeric total for summing spend later.
    record["total_amount"] = _parse_money(record.get("total"))

    # Store a complete backup of everything (including product + extras) so a
    # future field never gets silently dropped, and so free-text search works.
    backup = {**record, "extra_fields": extra_fields}
    record["raw_json"] = json.dumps(backup, default=str)

    return record

"""
config.py
---------
Loads settings from a local .env file so we never hard-code secrets
(like the Discord bot token) into the source code.

WHY THIS EXISTS:
- A bot token is like a password for your bot. If it ends up in code that
  gets shared or pushed to GitHub, anyone can control your bot.
- Keeping secrets in a .env file (which we git-ignore) is the standard,
  safe pattern. This file reads those values and hands them to the rest
  of the app.
"""

import os
from dotenv import load_dotenv  # from the python-dotenv package

# The project root is the folder ABOVE this src/ directory. We anchor the
# .env file, the database, and the exports folder to it so the app behaves
# the same no matter which directory you run it from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Reads the .env file in the project root and loads each KEY=value pair
# into the environment so os.getenv() below can see them.
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _require(name: str) -> str:
    """Fetch a required setting; fail loudly if it's missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required setting '{name}'. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


# --- Required settings (must be in your .env) ---

# The secret token for YOUR bot (from the Discord Developer Portal).
DISCORD_TOKEN: str = _require("DISCORD_TOKEN")

# The numeric ID of the channel where checkout webhooks are posted.
CHANNEL_ID: int = int(_require("CHANNEL_ID"))

# The numeric ID of your server ("guild" in Discord's API terms).
# Used to register the /export slash command instantly for just your server.
GUILD_ID: int = int(_require("GUILD_ID"))


# --- Optional settings (have sensible defaults) ---

# We only save embeds that look like a successful checkout. We detect that
# by checking whether this phrase appears in the embed's title/author/text.
# HiddenAIO uses "Successfully Checked Out", so "Checked Out" matches it.
SUCCESS_KEYWORD: str = os.getenv("SUCCESS_KEYWORD", "Checked Out")

# Where the SQLite database file lives (defaults to the project root).
DB_PATH: str = os.getenv("DB_PATH", os.path.join(PROJECT_ROOT, "checkouts.db"))

# Folder where exported .xlsx workbooks are written (defaults to project root).
EXPORT_DIR: str = os.getenv("EXPORT_DIR", os.path.join(PROJECT_ROOT, "exports"))

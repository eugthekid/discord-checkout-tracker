# Discord Checkout Tracker

A Discord bot that reads the "Successfully Checked Out" webhook cards your
checkout bot (e.g. HiddenAIO) posts into a channel, stores every one in a
local database, and lets you export **filtered** spreadsheets on demand with
a `/export` slash command.

Built as a learning project. The code is heavily commented — read it top to
bottom and you'll understand how Discord bots, embeds, databases, and Excel
generation fit together. See [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md).

---

## What it does

1. **Backfill** — on startup, reads the channel's entire history and saves
   every past checkout.
2. **Live logging** — stays connected and saves each new checkout the instant
   the webhook posts it.
3. **Export** — type `/export` in Discord with filters (profile, site, module,
   date range, free text) and it replies (privately, only to you) with a
   timestamped `.xlsx` attached — built in memory, no file saved on any device.
4. **Stats** — type `/stats` for an instant summary card (counts, spend, top
   profiles/sites) without opening a spreadsheet.

## The data flow

```
Checkout bot ──webhook──▶ Discord channel
                              │
                    (this bot reads it)
                              ▼
                    parse embed fields
                              ▼
                    SQLite database  (checkouts.db)
                              ▼
                 /export  ──filter──▶  Excel file (private reply in Discord)
```

## Project layout

| File | Job |
|------|-----|
| `src/config.py`   | Loads secrets/settings from `.env` |
| `src/database.py` | Stores & queries checkouts in SQLite |
| `src/parser.py`   | Turns a Discord embed into a clean record |
| `src/exporter.py` | Writes records into a formatted `.xlsx` |
| `src/stats.py`    | Aggregates checkouts for the `/stats` command |
| `src/bot.py`      | The bot: backfill, live logging, `/export` + `/stats` |
| `bot.sh`          | Start/stop the bot detached from your terminal |
| `docs/SETUP.md`   | **Start here** — how to create the bot in Discord |
| `docs/HOSTING.md` | Keep the bot running 24/7 (background, Pi, or cloud) |

---

## Quick start

> First time? Do the Discord side first: **[`docs/SETUP.md`](docs/SETUP.md)**.

```bash
# 1. From the project folder, create an isolated Python environment
python3 -m venv .venv
source .venv/bin/activate            # (Windows: .venv\Scripts\activate)

# 2. Install the libraries
pip install -r requirements.txt

# 3. Create your secrets file and fill it in
cp .env.example .env                 # then edit .env with your token + IDs

# 4. Run the bot
python src/bot.py
```

Leave it running. It backfills history, then logs new checkouts live.

### Running it in the background

`python src/bot.py` stops when you close the terminal. To keep it running after
you close the window, use the control script:

```bash
./bot.sh start     # run detached in the background
./bot.sh status    # is it running?
./bot.sh logs      # follow the live log (Ctrl+C to stop watching)
./bot.sh stop      # stop it
```

This survives closing the terminal, but **not** your Mac sleeping or shutting
off. For always-on (even with your computer off), see
[`docs/HOSTING.md`](docs/HOSTING.md).

## Using /export

In Discord, type `/export` and Discord will show the optional filter fields:

| Filter | Example | Meaning |
|--------|---------|---------|
| `profile`   | `Main`       | only that profile (partial match) |
| `site`      | `pokemon`    | only that site |
| `module`    | `PokemonCenter` | only that module |
| `date_from` | `2026-07-01` | on/after this date |
| `date_to`   | `2026-07-20` | on/before this date |
| `contains`  | `Charizard`  | free-text search across all fields |

Leave any filter blank to ignore it. `/export` with no filters exports
everything. The bot builds the `.xlsx` in memory and sends it back as a
**private (ephemeral) reply only you can see**, with the file attached plus the
count and total spend. Nothing is saved to disk on any device.

> **Heads-up on ephemeral messages:** because the reply is private, Discord
> treats it as temporary — it can disappear when you reload/restart the app, and
> it doesn't sync across devices the way a normal channel message does. So
> **download the file when you run the command.** If you'd rather have exports
> persist and be grabbable from any device later, we can switch `/export` back
> to posting in the channel.

## Using /stats

`/stats` takes the **same filters** as `/export` but, instead of a file, replies
with a summary card right in Discord: total checkouts, total spend, average order
value, and your top profiles and sites. Great for a quick "how did today go?"
without opening a spreadsheet.

```
/stats date_from:2026-07-20 date_to:2026-07-20     → just that day's numbers
/stats profile:Main                                 → totals for one profile
/stats                                               → all-time summary
```

## Notes

- **Dates are stored in UTC.** A checkout that shows 3:46 PM local in Discord
  may show a different clock time in the sheet. Filtering still works correctly
  because comparisons use absolute time.
- The bot must stay running to log live checkouts. History is always safe to
  re-scan — duplicates are impossible (keyed on Discord's message ID).

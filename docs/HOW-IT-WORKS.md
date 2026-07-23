# How it works (the learning doc)

This walks through the *concepts* behind the project, in the order they matter.
If you read one doc to actually learn something, read this one.

---

## 1. Webhook vs. bot — they're opposites

- A **webhook** is a write-only "mailbox slot." Your checkout software has a
  webhook URL and *POSTs* messages into a channel. A webhook cannot read
  anything. That green "Successfully Checked Out" card was delivered by a webhook.
- A **bot** is a full account that can *read* history, *listen* for new
  messages, and *respond*. That's what this project is.

So you already had the "write" half (the webhook). We built the "read" half.

## 2. Intents — asking Discord for permission to see things

When a bot connects, it declares **intents**: the categories of events it wants.
Most are on by default, but a few are **privileged** because they're sensitive.
`message_content` is privileged — it controls whether your bot can read the text
and embeds of messages. Because your data is *inside embeds*, we must:

1. Request it in code: `intents.message_content = True` (see `bot.py`), **and**
2. Enable it in the Developer Portal (see `SETUP.md` step 3).

Both are required. Forgetting the portal toggle is the classic beginner trap.

## 3. Embeds — why your data is easy to read

Discord messages can carry rich "embed" cards. An embed has a title, a
description, and a list of **fields**, where each field is a `name`/`value`
pair. Your checkout card is one embed whose fields are `Profile → Main`,
`Total → $80.82`, and so on.

This is the lucky break of the whole project: we don't have to parse messy
text. In `parser.py` we just loop over `embed.fields` and read values by name.
`FIELD_MAP` maps each Discord label to a database column.

## 4. Why a database sits in the middle

You wanted *different* exports depending on filters. Two designs were possible:

- **Naive:** every `/export` re-reads all of Discord, filters, writes Excel.
  Slow, hits rate limits, and re-does work constantly.
- **What we built:** read each checkout from Discord **once**, save it into a
  local SQLite database, and let every `/export` be a fast query against that
  local data. The spreadsheet becomes a disposable *view* of the database.

SQLite is a database that lives in one file (`checkouts.db`) and ships with
Python — nothing to install or run.

### De-duplication for free

Every Discord message has a unique numeric ID. We use it as the table's
**primary key** and insert with `INSERT OR REPLACE`. Result: re-running the
history backfill can't create duplicates — an already-seen checkout just
overwrites its identical self. That's why restarting the bot is always safe.

### One safety habit worth keeping forever

In `query_checkouts` we never paste your filter text into the SQL string. We use
`?` placeholders and pass values separately. This blocks **SQL injection**, where
crafted input could otherwise change the query. It's the single most important
reflex when any user input touches a database.

## 5. The two ways data comes in

- **Backfill** (`backfill_history`): `channel.history(limit=None,
  oldest_first=True)` streams every past message so we catch up on old checkouts.
- **Live** (`on_message`): fires once per new message; we store it immediately.

Both funnel through the same `_maybe_parse` → `upsert_checkout` path, so there's
exactly one place that decides "is this a checkout, and what does it contain?"

## 6. Slash commands — the modern way to take input

`/export` is an **application (slash) command**. Two things to know:

- **Registration & the 1-hour rule.** Global commands can take up to an hour to
  appear across Discord. We register to your specific server ("guild") instead,
  which is instant. That's `setup_hook` calling `tree.sync(guild=...)`.
- **The 3-second rule.** Discord expects an initial response within 3 seconds or
  it shows "the application did not respond." Since building a spreadsheet might
  take longer, we call `interaction.response.defer()` first ("working on it…"),
  then send the real result with `interaction.followup.send()`.

`ephemeral=True` makes those replies visible only to you, not the whole channel.

## 6b. Building an embed (the reverse of reading one)

`/export` reads embeds; `/stats` *builds* one. In `stats_command` we create a
`discord.Embed`, give it a title and color, and `add_field(name, value, inline)`
for each stat — the exact same structure HiddenAIO uses to post your checkout
cards. `inline=True` lets small fields (Checkouts / Total Spend / Avg Order) sit
side-by-side; `inline=False` gives the breakdown lists their own full-width rows.

The data itself comes from `stats.py`, which does its counting **in SQL** with
`COUNT()`, `SUM()`, and `GROUP BY` rather than looping in Python. And because
`/stats` and `/export` share the same `_build_filters` helper in `database.py`,
a filter like `profile:Main` means exactly the same thing in both commands —
that's the payoff of not repeating yourself.

## 7. Generating the Excel file

`exporter.py` uses **openpyxl** to build a real `.xlsx`. Beyond dumping rows it
does three "polish" things: a frozen, styled header row; a summary row with the
count and total spend; and a timestamped filename so exports never overwrite
each other.

---

## Where you'd extend this next (ideas)

- **Upload the file back into Discord** — a one-line change: pass the path to
  `discord.File(path)` in the `/export` followup. (You chose local-only for now.)
- **Daily spend trend in `/stats`** — add a `GROUP BY` on the date to show a
  per-day breakdown alongside the per-profile and per-site ones.
- **Deduplicate real orders** — if the same order posts twice, key on `Order #`.
- **Dashboards** — point a tool at `checkouts.db`, or schedule a daily export.

> ✅ **Already built:** a `/stats` command (checkouts + spend per profile/site).
> See section 6b above.

## Glossary

| Term | Meaning |
|------|---------|
| Webhook | Write-only URL that posts messages into a channel |
| Bot / Client | An account that can read and respond |
| Intent | A category of events a bot asks Discord to send it |
| Embed | A structured "card" message with fields |
| Guild | Discord's internal word for a server |
| Slash command | A `/command` users invoke, with typed arguments |
| SQLite | A tiny file-based database built into Python |
| Primary key | A column whose value uniquely identifies each row |

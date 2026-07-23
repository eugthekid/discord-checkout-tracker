# Case Study: Discord Checkout Tracker

> A portfolio write-up framed for product management recruiting. This is the
> narrative version of the project — the *why* and *how I thought about it*,
> not just the *what*. Copy any section into your portfolio site and swap the
> bracketed placeholders for your real numbers.

**Role:** Sole builder — product, design, and engineering
**Timeline:** [e.g. ~1 week, July 2026]
**Stack:** Python · discord.py · SQLite · openpyxl
**Repo:** [link to your GitHub]

---

## TL;DR

I run a small sneaker/collectible reselling operation. My automated checkout
software already posted a "Successfully Checked Out" card into a private Discord
channel every time it purchased an item — but those records were trapped in
chat, impossible to total or filter. I built a Discord bot that captures every
one of those cards into a local database and lets me export filtered
spreadsheets and pull instant stats. It turned a scroll-and-guess chat log into
a queryable record of what I bought, for how much, on which profile.

---

## The problem

Every successful purchase produced a rich Discord card with ~15 fields
(product, total, profile, site, order #, timestamp, and more). Useful
individually — useless in aggregate:

- **No totals.** "How many checkouts this week? How much did I spend?" meant
  manually scrolling and counting.
- **No filtering.** I couldn't answer "how did my *Main* profile do on
  *Pokémon Center* last month?" without reading every message.
- **No export.** Nothing fed into a spreadsheet for bookkeeping or resale
  planning.

The data existed; it just wasn't *accessible as data*.

## Who it's for

Primary user: me, the operator, who needs fast answers between drops.
The design generalizes to any reseller whose checkout tooling posts webhook
receipts to Discord — a common setup in the community.

## Goals & non-goals

| Goals | Non-goals (deliberately cut) |
|-------|------------------------------|
| Capture every checkout automatically, no manual entry | A hosted web dashboard |
| Filter by profile, site, module, date, and free text | Multi-user / multi-server support |
| Export filtered spreadsheets on demand | Real-time charts |
| Never lose or double-count a record | Editing/deleting records |

Scoping *out* the dashboard and multi-user support kept v1 shippable in days
instead of weeks — the classic MVP trade-off.

## Key product decisions (and the trade-offs)

**1. A database in the middle, not chat-to-Excel directly.**
The naive build would re-read all of Discord on every export. I chose to
capture each checkout *once* into a local SQLite database, making every export
a fast local query. Cost: a bit more upfront structure. Payoff: instant,
unlimited re-filtering and no API rate-limit pain.

**2. Capture everything, filter at export time.**
Rather than deciding up front which fields matter, I store all of them (plus a
JSON backup of any *unrecognized* field). This means a future change to the
source cards can't silently break me, and new filter ideas need no re-scraping.

**3. Slash command over a command-line tool.**
I could have shipped a terminal script faster. I chose an in-Discord `/export`
(and later `/stats`) command so the tool lives *where the data already is* —
no context-switching, usable from my phone. Cost: learning Discord's
application-command model (registration timing, the 3-second response rule).

**4. Idempotency by design.**
Every record is keyed on Discord's unique message ID, so re-running the history
scan can never create duplicates. This removed a whole category of "did I
double-count?" anxiety and made the backfill safe to run anytime.

## What I built

- **Automatic capture** — on startup the bot backfills the channel's full
  history; it then logs each new checkout live as it arrives.
- **`/export`** — filter by profile / site / module / date range / free text and
  get a formatted, timestamped Excel workbook (styled header, summary row with
  count and total spend).
- **`/stats`** — the same filters, but an instant in-Discord summary card:
  total checkouts, total spend, average order value, and top profiles/sites.

## Testing & iteration

I built the risky data path (parse → store → filter → export) to be testable
*without* a live Discord connection, then drove it with a fabricated checkout
that mirrored a real card. That test suite verified:

- correct field extraction from the embed, including money parsing (`$80.82` → `80.82`)
- de-duplication (re-storing the same message is a no-op)
- profile and date-range filtering returning the right subsets
- the exported spreadsheet's contents on read-back

**Iteration:** after the export MVP worked, I added `/stats`. Rather than
duplicate the filter logic, I refactored the query layer so `/export` and
`/stats` share one filter builder — the same `profile:Main` means the same
thing everywhere. Small change, meaningfully lower maintenance risk.

## Outcomes

- Reduced "how many checkouts / how much spend" from *minutes of scrolling* to
  *one command*.
- [X] checkouts and [$Y] in purchases now queryable across [N] profiles.
- Filtered exports feed directly into my resale bookkeeping.

*(Fill in the bracketed figures once you've run it on your real channel.)*

## What I'd do next

- Per-day spend trend in `/stats` (another `GROUP BY`).
- Post the exported file back into Discord for phone access.
- Deduplicate on real order numbers, not just message IDs.

## What I learned (PM lens)

- **Ruthless scoping ships product.** Cutting the dashboard and multi-user
  support is why this exists at all.
- **Design for the data you don't know yet.** Storing every field + a JSON
  backup made the system resilient to upstream changes I don't control.
- **Meet users where they are.** Putting the tool inside Discord, not a
  terminal, is the difference between something I'd actually use and something
  I'd abandon.
- **Invest in the risky path's testability first.** Being able to verify the
  parse/store/export pipeline without a live bot made iteration fast and safe.

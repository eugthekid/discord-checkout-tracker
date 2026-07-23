"""
bot.py
------
The main program. This is the actual Discord bot. It does three jobs:

  1. BACKFILL  -- when it starts, it reads the channel's whole history and
                  saves every past checkout into the database.
  2. LIVE      -- it then stays connected and saves each NEW checkout the
                  moment a webhook posts it.
  3. EXPORT    -- it registers /export (uploads a filtered .xlsx into Discord)
                  and /stats (a summary card) slash commands you type in Discord.

Run it with:  python src/bot.py
Stop it with: Ctrl+C
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional

# Make sure Python can import our sibling modules (config, database, ...)
# regardless of which folder you launched the script from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import discord
from discord import app_commands

import config
import database
import parser as checkout_parser
import exporter
import stats


# --- Intents: the permissions our bot asks Discord for. ---
# message_content is a "privileged intent": you MUST turn it on in the
# Developer Portal too, or the bot will connect but see empty messages.
# We need it because the checkout data lives inside message embeds.
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True


class CheckoutBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        # The "command tree" holds our slash commands.
        self.tree = app_commands.CommandTree(self)
        self._backfilled = False  # guard so backfill runs only once

    async def setup_hook(self) -> None:
        """
        Runs once, before the bot connects. We register the /export command
        to just YOUR server (guild) so it appears instantly -- global
        commands can take up to an hour for Discord to roll out.
        """
        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        """Runs every time the bot connects. We backfill history once."""
        print(f"Logged in as {self.user}. Reading channel history...")
        if self._backfilled:
            return
        self._backfilled = True
        await self.backfill_history()

    def _channels_to_scan(self, guild: discord.Guild) -> list[discord.abc.Messageable]:
        """Decide which channels to read: the whole server, or a fixed list."""
        if config.SCAN_ALL_CHANNELS:
            # Every regular text channel in the server.
            return list(guild.text_channels)
        # Just the specific IDs from config (skip any we can't find).
        channels = []
        for cid in config.CHANNEL_IDS:
            ch = self.get_channel(cid)
            if ch is not None:
                channels.append(ch)
        return channels

    async def backfill_history(self) -> None:
        """Read history across all watched channels and store every checkout."""
        guild = self.get_guild(config.GUILD_ID)
        if guild is None:
            print(f"Could not find server {config.GUILD_ID}. Is the bot in it?")
            return

        channels = self._channels_to_scan(guild)
        scope = "all channels" if config.SCAN_ALL_CHANNELS else f"{len(channels)} channel(s)"
        print(f"Scanning {scope} in {guild.name}...")

        total_seen = 0
        total_new = 0
        for channel in channels:
            try:
                # oldest_first=True walks from the start; limit=None means "all".
                async for message in channel.history(limit=None, oldest_first=True):
                    record = _maybe_parse(message)
                    if record:
                        total_seen += 1
                        if database.upsert_checkout(record):
                            total_new += 1
            except discord.Forbidden:
                # The bot can't read this channel -- skip it and keep going.
                print(f"  (no access to #{channel.name}, skipping)")
            except discord.HTTPException as exc:
                print(f"  (error reading #{channel.name}: {exc}, skipping)")

        print(
            f"Backfill complete: {total_seen} checkouts found, "
            f"{total_new} new, {total_seen - total_new} already stored."
        )
        print("Now listening for new checkouts. Type /stats or /export in Discord.")

    async def on_message(self, message: discord.Message) -> None:
        """Runs for every new message. We store it if it's a checkout."""
        # Only our server, and only channels we're configured to watch.
        if message.guild is None or message.guild.id != config.GUILD_ID:
            return
        if not config.should_scan(message.channel.id):
            return
        record = _maybe_parse(message)
        if record and database.upsert_checkout(record):
            profile = record.get("profile") or "?"
            channel_name = record.get("channel_name") or "?"
            print(
                f"Logged new checkout in #{channel_name}: "
                f"{record.get('product')} (profile: {profile})"
            )


def _maybe_parse(message: discord.Message) -> Optional[dict]:
    """Parse a message only if its embed looks like a successful checkout."""
    if not message.embeds:
        return None
    if not checkout_parser.looks_like_checkout(message.embeds[0], config.SUCCESS_KEYWORD):
        return None
    return checkout_parser.parse_message(message)


def _parse_date_range(
    date_from: Optional[str], date_to: Optional[str]
) -> tuple[Optional[float], Optional[float]]:
    """
    Convert "YYYY-MM-DD" strings into unix timestamps for filtering.
    The 'from' date starts at 00:00; the 'to' date includes the whole day.
    """
    from_ts = None
    to_ts = None
    if date_from:
        from_ts = datetime.strptime(date_from, "%Y-%m-%d").timestamp()
    if date_to:
        # Add a full day so the 'to' date is inclusive of everything that day.
        end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        to_ts = end.timestamp() - 1  # last second of the given day
    return from_ts, to_ts


# --- Create the bot instance, then define the /export slash command on it ---
bot = CheckoutBot()


@bot.tree.command(name="export", description="Export filtered checkouts to an Excel file")
@app_commands.describe(
    profile="Only include this profile (partial match)",
    site="Only include this site (partial match)",
    module="Only include this module (partial match)",
    channel="Only include this channel name (partial match)",
    date_from="Start date, format YYYY-MM-DD",
    date_to="End date, format YYYY-MM-DD",
    contains="Free-text search across all fields",
)
async def export_command(
    interaction: discord.Interaction,
    profile: Optional[str] = None,
    site: Optional[str] = None,
    module: Optional[str] = None,
    channel: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    contains: Optional[str] = None,
) -> None:
    """This function runs when you type /export in Discord."""
    # Tell Discord "I'm working on it" so it doesn't time out after 3 seconds.
    # ephemeral=True keeps the whole reply (including the attached file) private
    # to you -- nobody else in the channel sees it.
    await interaction.response.defer(ephemeral=True)

    try:
        from_ts, to_ts = _parse_date_range(date_from, date_to)
    except ValueError:
        await interaction.followup.send(
            "Date must be in YYYY-MM-DD format, e.g. 2026-07-20.", ephemeral=True
        )
        return

    rows = database.query_checkouts(
        profile=profile,
        site=site,
        module=module,
        channel=channel,
        date_from_ts=from_ts,
        date_to_ts=to_ts,
        contains=contains,
    )

    if not rows:
        await interaction.followup.send(
            "No checkouts matched those filters.", ephemeral=True
        )
        return

    # Build a short label from the filters so the filename is meaningful.
    label = "_".join(v for v in [profile, site, module, channel, contains] if v) or "all"

    # Build the .xlsx entirely in memory (no disk), then wrap those bytes in a
    # discord.File so we can upload it as an attachment.
    buffer, filename, count, spend = exporter.export_to_buffer(rows, label=label)
    discord_file = discord.File(buffer, filename=filename)

    filters_used = ", ".join(
        f"{k}={v}"
        for k, v in {
            "profile": profile, "site": site, "module": module, "channel": channel,
            "from": date_from, "to": date_to, "contains": contains,
        }.items()
        if v
    ) or "none"

    await interaction.followup.send(
        f"Exported **{count}** checkouts (total spend **${spend:,.2f}**).\n"
        f"Filters: {filters_used}",
        file=discord_file,  # the spreadsheet is attached to this message
        ephemeral=True,     # private to you
    )


@bot.tree.command(name="stats", description="Show checkout stats (optionally filtered)")
@app_commands.describe(
    profile="Only count this profile (partial match)",
    site="Only count this site (partial match)",
    module="Only count this module (partial match)",
    channel="Only count this channel name (partial match)",
    date_from="Start date, format YYYY-MM-DD",
    date_to="End date, format YYYY-MM-DD",
    contains="Free-text search across all fields",
)
async def stats_command(
    interaction: discord.Interaction,
    profile: Optional[str] = None,
    site: Optional[str] = None,
    module: Optional[str] = None,
    channel: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    contains: Optional[str] = None,
) -> None:
    """Runs when you type /stats. Replies with a summary embed (private to you)."""
    await interaction.response.defer(ephemeral=True)

    try:
        from_ts, to_ts = _parse_date_range(date_from, date_to)
    except ValueError:
        await interaction.followup.send(
            "Date must be in YYYY-MM-DD format, e.g. 2026-07-20.", ephemeral=True
        )
        return

    data = stats.compute_stats(
        profile=profile, site=site, module=module, channel=channel,
        date_from_ts=from_ts, date_to_ts=to_ts, contains=contains,
    )

    if data["count"] == 0:
        await interaction.followup.send(
            "No checkouts matched those filters.", ephemeral=True
        )
        return

    # --- BUILDING an embed (the opposite of parsing one). ---
    # We create a card with a title and add labeled fields, exactly like the
    # cards HiddenAIO posts. inline=True lets fields sit side by side.
    embed = discord.Embed(
        title="📊 Checkout Stats",
        color=0x57F287,  # Discord green
    )
    embed.add_field(name="Checkouts", value=str(data["count"]), inline=True)
    embed.add_field(name="Total Spend", value=f"${data['total_spend']:,.2f}", inline=True)
    embed.add_field(name="Avg Order", value=f"${data['avg_order_value']:,.2f}", inline=True)
    embed.add_field(
        name="Top Profiles",
        value=stats.format_breakdown(data["by_profile"]),
        inline=False,
    )
    embed.add_field(
        name="Top Sites",
        value=stats.format_breakdown(data["by_site"]),
        inline=False,
    )
    embed.add_field(
        name="Top Channels",
        value=stats.format_breakdown(data["by_channel"]),
        inline=False,
    )

    filters_used = ", ".join(
        f"{k}={v}"
        for k, v in {
            "profile": profile, "site": site, "module": module, "channel": channel,
            "from": date_from, "to": date_to, "contains": contains,
        }.items()
        if v
    ) or "none"
    embed.set_footer(text=f"Filters: {filters_used}")

    await interaction.followup.send(embed=embed, ephemeral=True)


def main() -> None:
    database.init_db()  # create the table if needed
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()

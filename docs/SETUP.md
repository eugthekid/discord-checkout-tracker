# Setup: creating your Discord bot

This is the part **you** have to do by hand — it involves your Discord account,
which I can't (and shouldn't) log into. It takes about 10 minutes. Follow it
once and you're done.

There are two "halves" to a Discord bot:
- **The application/bot** you create in Discord's Developer Portal (gives you a
  secret token).
- **The invite** that adds that bot into your server with the right permissions.

---

## 1. Create the application

1. Go to <https://discord.com/developers/applications>.
2. Click **New Application**, give it a name (e.g. "Checkout Tracker"), Create.

## 2. Turn it into a bot and get the token

1. In the left sidebar, click **Bot**.
2. Click **Reset Token**, confirm, and **copy** the token that appears.
   - This is your `DISCORD_TOKEN`. Treat it like a password.
   - Paste it into your `.env` file: `DISCORD_TOKEN=...`
   - If you ever leak it, come back and Reset Token again — the old one dies.

## 3. Enable the Message Content Intent (critical!)

Still on the **Bot** page, scroll to **Privileged Gateway Intents**:

1. Turn **ON** → **Message Content Intent**.
2. Click **Save Changes**.

> **Why this matters:** Discord hides the *content* of messages (including embed
> fields) from bots by default, for privacy. Your checkout data lives inside
> embeds, so without this intent the bot connects fine but sees blank messages.
> This is the #1 reason a beginner's bot "sees nothing."

## 4. Invite the bot to your server

1. Left sidebar → **OAuth2** → **URL Generator**.
2. Under **Scopes**, check:
   - `bot`
   - `applications.commands`  ← needed for the `/export` slash command
3. Under **Bot Permissions**, check:
   - **View Channels**
   - **Read Message History**
   - **Send Messages** (so `/export` and `/stats` can reply)
   - **Attach Files** (so `/export` can upload the spreadsheet into Discord)
4. Copy the generated URL at the bottom, open it in your browser, pick your
   server, and click **Authorize**.

## 5. Get your Channel ID and Server ID

Discord hides IDs until you enable Developer Mode:

1. Discord app → **User Settings** (gear) → **Advanced** → turn on **Developer Mode**.
2. **Right-click your server's icon** → **Copy Server ID** → this is `GUILD_ID`.
3. **Right-click the checkout channel** → **Copy Channel ID** → this is `CHANNEL_ID`.
4. Put both into your `.env`.

## 6. Double-check channel access

Make sure the bot's role can actually *see* the checkout channel. If the
channel is private, right-click it → **Edit Channel → Permissions**, and add the
bot (or its role) with **View Channel** + **Read Message History**.

---

## Your finished .env should look like

```
DISCORD_TOKEN=MTIzNDU2Nzg5...your-real-token
CHANNEL_ID=112233445566778899
GUILD_ID=998877665544332211
```

Now go back to the [README](../README.md#quick-start) and run the bot.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Bot connects but backfill finds 0 checkouts | Message Content Intent is off (step 3), or wrong `CHANNEL_ID` |
| `/export` doesn't appear in Discord | Missing `applications.commands` scope (step 4), or wrong `GUILD_ID` |
| `PrivilegedIntentsRequired` error on startup | Message Content Intent is off in the portal |
| `Missing required setting 'DISCORD_TOKEN'` | You haven't created/filled `.env` yet |

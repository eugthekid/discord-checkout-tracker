# Hosting: keeping the bot running 24/7

This guide is about making the bot run **even when your own computer is off**.

First, get the vocabulary straight, because it trips everyone up:

| Term | What it means | Survives closing the terminal? | Survives your Mac sleeping/off? |
|------|---------------|:---:|:---:|
| **Foreground** (`python src/bot.py`) | Runs tied to the terminal window | ❌ | ❌ |
| **Detached** (`./bot.sh start`, uses `nohup &`) | Runs in the background on your Mac | ✅ | ❌ |
| **Hosted** (runs on another always-on machine) | Lives in the cloud / on a Pi | ✅ | ✅ |

`./bot.sh start` already gives you the middle row. This guide is about the last
row. **Key idea: a Discord bot makes an *outbound* connection to Discord**, so
hosting one needs no public IP, no open ports, and no domain — just a machine
with power and internet that stays on.

---

## The catch with a laptop

On a MacBook, `./bot.sh start` keeps the bot alive when you *close the terminal*,
but the moment the lid closes (or the machine idles into sleep), macOS suspends
the process and the bot drops offline. Two partial workarounds on the Mac
itself:

- **Prevent idle sleep while it runs:** launch it wrapped in `caffeinate`:
  ```bash
  caffeinate -i ./bot.sh start
  ```
  `-i` prevents *idle* sleep. Note: closing the lid still sleeps the Mac unless
  it's plugged in with the right Energy settings, so this is a stopgap, not a
  real 24/7 answer.
- **Run it as a launchd service** (the Mac-native "keep this alive and restart
  it on crash / at login" system). More robust than `nohup`, but it still can't
  beat the machine being powered off.

For genuine always-on, you want a machine that's *meant* to stay on. Options
below, cheapest-effort first.

---

## Option A — A Raspberry Pi (or an old laptop) at home

Best learning value, ~zero ongoing cost if you already have the hardware.

1. Install Python 3 on the device.
2. Copy the project folder over (or `git clone` it once it's on GitHub).
3. Recreate the setup there:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # then paste in your token + IDs
   ```
4. Keep it running with the OS's service manager so it survives reboots. On a
   Raspberry Pi / Linux that's **systemd** — see the sample unit at the bottom.

The device just needs to stay plugged in and on your home Wi-Fi. That's it.

## Option B — A small cloud host (no hardware needed)

A tiny always-on Linux server in a datacenter. Two flavors:

- **A "platform" host (easiest):** services like **Railway**, **Render**, or
  **Fly.io** let you point them at your GitHub repo, set your `.env` values as
  "environment variables" in their dashboard, and they run it for you. Often a
  free or a few-dollars-a-month tier is enough for one small bot. This is the
  fastest path and you never touch a server directly.
- **A raw VPS (most control):** a ~$4–6/month virtual machine from providers
  like DigitalOcean, Hetzner, or Linode. You SSH in and set it up exactly like
  the Raspberry Pi steps above, using **systemd** to keep it alive.

> Whichever you pick, your bot token goes into the host's environment-variable
> settings or its own `.env` on that machine — **never commit `.env` to GitHub.**
> That's why `.gitignore` excludes it.

---

## Keeping it alive with systemd (Linux hosts)

On a Raspberry Pi or a Linux VPS, create a service file so the bot starts on
boot and restarts if it ever crashes. Save as
`/etc/systemd/system/checkout-bot.service` (adjust the paths and user):

```ini
[Unit]
Description=Discord Checkout Tracker bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/discord-checkout-tracker
ExecStart=/home/youruser/discord-checkout-tracker/.venv/bin/python -u src/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable checkout-bot     # start automatically on boot
sudo systemctl start checkout-bot      # start it now
sudo systemctl status checkout-bot     # check it's healthy
journalctl -u checkout-bot -f          # follow its logs
```

`Restart=always` means if the bot ever errors out, systemd relaunches it after
5 seconds — the closest thing to hands-off reliability.

---

## A note on the database when hosting

Your `checkouts.db` lives next to the bot. If you host on a new machine, it
starts with an empty database — but that's fine: on first run the **backfill**
re-reads your whole Discord channel and rebuilds it. You won't lose history as
long as the messages still exist in Discord.

## Which should you pick?

- **Just want it reliable with least fuss?** A platform host (Railway/Render).
- **Want to learn deployment and have a Pi / spare laptop?** Option A — it's the
  most educational and makes the best portfolio story ("built it, then deployed
  it as a systemd service on a Raspberry Pi").
- **Want a real server to manage?** A cheap VPS + systemd.

When you're ready, tell me which route and I'll walk you through it step by step.

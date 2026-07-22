# AIMS Local Print Agent

Bridges the AIMS cloud backend to printers on your restaurant's own WiFi/LAN.
The backend is hosted on the internet and can never reach a private
`192.168.x.x` printer address directly — this agent runs on any always-on PC
in your shop, connects out to AIMS, and relays print jobs to the printer for
you. No router configuration, port-forwarding, or VPN required — the
connection is always initiated from inside your shop, outward.

## Setup

1. Install Python 3.9+ if it isn't already, then:
   ```
   pip install -r requirements.txt
   ```
2. In the AIMS web app: **Settings → Printers → Local Print Agent → Pair a
   New Agent**. Copy the token or download `agent-config.json`, and place
   that file in this same folder (next to `agent.py`).
3. Run it:
   ```
   python agent.py
   ```
   You should see `Connected — waiting for print jobs.` Leave this window
   open — printing only works while it's running. The Settings page will
   show the agent as **Connected**.

## Running it in the background / at startup

The terminal window needs to stay open (or run this as a background
service) for printing to keep working. Two simple options:

**Windows** — put a shortcut to a `.bat` file like this in your Startup
folder (`Win+R` → `shell:startup`):
```bat
cd /d "C:\path\to\print-agent"
python agent.py
```

**macOS** — add a LaunchAgent (`~/Library/LaunchAgents/com.aims.printagent.plist`)
that runs `python3 /path/to/print-agent/agent.py` at login, or simply run it
in a Terminal tab you leave open.

A packaged single-file executable (no Python install required) can be built
with:
```
pip install pyinstaller
pyinstaller --onefile agent.py
```
The resulting binary in `dist/` still expects `agent-config.json` next to
it (or pass `--config /path/to/agent-config.json`).

## Troubleshooting

- **"Config file not found"** — make sure `agent-config.json` is in the same
  folder as `agent.py`, or pass `--config`.
- **Stuck on "Connecting..."** — check your internet connection; the agent
  connects outbound to the AIMS server, same as any browser tab.
- **Settings page shows "Paired — offline"** — the agent isn't running (or
  lost its connection). Restart it.
- **A specific ticket fails with "Could not reach `<printer name>`"** — the
  agent connected fine, but couldn't reach that printer's IP from your shop's
  network. Check the printer is powered on and its IP/port in Settings →
  Printers is still correct.
- **Regenerating the token in Settings** immediately invalidates the old
  one — download the new config and restart the agent with it.

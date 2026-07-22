# AIMS Local Print Agent

Bridges the AIMS cloud backend to printers on a restaurant's own WiFi/LAN.
The backend is hosted on the internet and can never reach a private
`192.168.x.x` printer address directly — this agent runs on any always-on PC
in the shop, connects **out** to AIMS, and relays print jobs to the printer.
No router configuration, port-forwarding, or VPN needed — the connection is
always initiated from inside the shop, outward.

```
AIMS (cloud)  ←──── outbound WebSocket ────  agent.exe (shop PC)
                                                     │
                                                     ▼ raw socket, LAN-local
                                              192.168.1.23:9100 (printer)
```

---

## Connecting an agent (shop staff / setup on a Windows PC)

You need two files in the **same folder**:

| File | Where it comes from | Same for every shop? |
|---|---|---|
| `aims-print-agent.exe` | [Download link — ask your AIMS admin] | Yes, one file for everyone |
| `agent-config.json` | Paired fresh per shop (see below) | No, unique per shop — never share one shop's file with another |

### Step 1 — Pair this shop and get its config file

1. Log into AIMS as an admin for **this shop's tenant**.
2. Go to **Settings → Printers**, scroll to the **Local Print Agent** card.
3. Click **Pair a New Agent**.
4. A dialog shows a one-time token. Click **Download agent-config.json**.
   > This token is shown once and never again. If you lose the file, come
   > back to this screen and click **Regenerate Token** to get a new one —
   > the old one stops working immediately.

### Step 2 — Run the agent

1. Put `aims-print-agent.exe` and the `agent-config.json` you just
   downloaded into the same folder (e.g. Desktop, or `C:\AIMS-Agent\`).
2. Double-click `aims-print-agent.exe`.
3. **Windows will likely show "Windows protected your PC" (SmartScreen).**
   This is expected for a new, unsigned executable — click **More info →
   Run anyway**.
4. A black console window opens. Wait for it to say:
   ```
   Connected — waiting for print jobs.
   ```
5. Leave that window open — printing only works while it's running.

### Step 3 — Verify it's connected

Back in AIMS, **Settings → Printers → Local Print Agent** should now show
a green **Connected** chip (refresh the page if it still says "Paired —
offline").

### Step 4 — Test print

1. Under the **Kitchen Printer** / **Bar Printer** card (same Printers
   settings page), make sure the printer's IP address and port are correct
   for this shop's actual network, then click **Test Print**.
2. You should get a toast saying **"Test ticket sent to `<printer name>`."**
   and the physical printer should print a short test ticket.
3. If it works, print a real KOT/BOT from Kitchen Display, Waiter Order Pad,
   or Live Orders as normal — it now prints for real instead of falling
   back to the browser's print dialog.

---

## Keeping it running (start automatically, no manual double-click)

The console window needs to keep running for printing to work — closing it
disconnects the agent. To have it start automatically when the PC boots:

1. Press `Win + R`, type `shell:startup`, press Enter — this opens the
   Startup folder.
2. Create a shortcut to `aims-print-agent.exe` inside that folder.

Now it launches automatically every time the shop PC starts, with no one
needing to remember to double-click it each morning.

---

## Troubleshooting

| Symptom | What's happening | Fix |
|---|---|---|
| "Config file not found" | `agent-config.json` isn't next to the `.exe` | Move it into the same folder, or run with `--config path\to\agent-config.json` |
| Stuck on "Connecting..." | No internet, or a firewall is blocking outbound WebSocket traffic | Check the PC's internet connection; same connectivity a browser tab needs |
| AIMS shows "Paired — offline" | The agent isn't running right now (closed, PC restarted, etc.) | Re-launch `aims-print-agent.exe` |
| Print fails: "Could not reach `<printer name>`" | Agent is connected fine, but can't reach *that specific printer's* IP on the shop's LAN | Check the printer is powered on, on the same WiFi/network, and its IP/port in Settings → Printers is still correct |
| Print fails: "No print agent is connected" | No agent has pinged in recently — either never paired, or genuinely offline | Follow "Connecting an agent" above |
| Windows SmartScreen / antivirus flags the `.exe` | Expected — it isn't code-signed | Click "More info → Run anyway" (SmartScreen) or add an exception (antivirus) |
| Google Drive shows "can't scan for viruses" before download | Normal Drive behavior for `.exe` files | Click "Download anyway" |

**Regenerating a token** (Settings → Printers → Local Print Agent →
Regenerate Token) immediately invalidates the old one — the currently
running agent will need the new `agent-config.json` and a restart to
reconnect.

---

## For developers — running from source / building the `.exe`

Only needed if you're changing `agent.py` itself, not for connecting a
shop's PC (use the prebuilt `.exe` above for that).

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python agent.py                  # expects agent-config.json next to it,
                                  # or pass --config /path/to/it
```

**Building the Windows `.exe`**: pushing to `main` (or tagging `vX.Y.Z`)
triggers `.github/workflows/build-windows.yml`, which builds on a real
Windows GitHub Actions runner via PyInstaller and uploads `agent.exe` as a
workflow artifact (and, for version tags, publishes it to the repo's
Releases page). To build locally on Windows instead:
```
pip install pyinstaller
pyinstaller --onefile --name agent agent.py
```
Output lands in `dist/agent.exe`.

Protocol reference (mirrors `apps/kds/consumers.py::PrintAgentConsumer` in
the main AIMS backend repo):

```
Client → server:
    {"type": "ping"}
    {"type": "print_result", "job_id": ..., "ok": bool, "message": str}

Server → client:
    {"type": "print_job", "job_id", "printer_id", "printer_name",
     "ip_address", "port", "payload_b64"}
```

#!/usr/bin/env python3
"""
AIMS Local Print Agent

Runs on any always-on PC inside a restaurant's own WiFi/LAN. The AIMS
backend is cloud-hosted and can never open a socket directly to a printer's
private 192.168.x.x address — this agent bridges that gap: it opens an
outbound WebSocket connection to the backend (so no port-forwarding or VPN
is needed on the restaurant's router) and waits for print jobs, which it
then delivers to the actual printer over the LAN it's running on, exactly
the way the backend used to do it directly (raw ESC/POS bytes over a plain
TCP socket to the printer's IP:port).

Setup
-----
1. pip install -r requirements.txt
2. Pair an agent from Settings > Printers > Local Print Agent in the AIMS
   web app, download the resulting agent-config.json, and place it next to
   this script (or pass --config /path/to/agent-config.json).
3. python agent.py

agent-config.json shape:
    {"tenant_id": "...", "token": "...", "ws_url": "wss://host/ws/kds/print-agent/"}

Protocol (mirrors apps/kds/consumers.py::PrintAgentConsumer)
-------------------------------------------------------------
Client -> server:
    {"type": "ping"}
    {"type": "print_result", "job_id": ..., "ok": bool, "message": str}

Server -> client:
    {"type": "print_job", "job_id", "printer_id", "printer_name",
     "ip_address", "port", "payload_b64"}
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlencode

import certifi

try:
    import websockets
except ImportError:
    print("Missing dependency — run: pip install -r requirements.txt", file=sys.stderr)
    raise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("print-agent")

PING_INTERVAL_SECONDS = 20
PRINTER_SOCKET_TIMEOUT_SECONDS = 5
RECONNECT_MIN_SECONDS = 2
RECONNECT_MAX_SECONDS = 30


def load_config(path: Path) -> dict:
    if not path.exists():
        log.error(
            "Config file not found: %s\n"
            "Pair an agent in AIMS (Settings > Printers > Local Print Agent), "
            "download agent-config.json, and place it next to this script.",
            path,
        )
        sys.exit(1)
    with path.open() as f:
        config = json.load(f)
    missing = [k for k in ("tenant_id", "token", "ws_url") if not config.get(k)]
    if missing:
        log.error("Config file %s is missing: %s", path, ", ".join(missing))
        sys.exit(1)
    return config


def deliver_to_printer(ip_address: str, port: int, payload: bytes) -> None:
    """Exactly what apps/kds/printing.py::send_to_printer did — just running
    on the LAN this time, so it can actually reach the printer."""
    with socket.create_connection((ip_address, port), timeout=PRINTER_SOCKET_TIMEOUT_SECONDS) as sock:
        sock.sendall(payload)


async def handle_print_job(ws, job: dict) -> None:
    job_id = job.get("job_id")
    printer_name = job.get("printer_name") or "printer"
    ip_address = job.get("ip_address")
    port = job.get("port")

    try:
        payload = base64.b64decode(job["payload_b64"])
        deliver_to_printer(ip_address, int(port), payload)
    except OSError as exc:
        log.warning("Could not reach %s at %s:%s — %s", printer_name, ip_address, port, exc)
        result = {
            "type": "print_result", "job_id": job_id, "ok": False,
            "message": f"Could not reach {printer_name} ({ip_address}:{port}). "
                       "Check it's powered on and connected to the network.",
        }
    except Exception as exc:  # malformed job, decode failure, etc. — never crash the connection over one bad job
        log.exception("Unexpected error handling print job %s", job_id)
        result = {"type": "print_result", "job_id": job_id, "ok": False, "message": f"Agent error: {exc}"}
    else:
        log.info("Printed to %s (%s:%s)", printer_name, ip_address, port)
        result = {"type": "print_result", "job_id": job_id, "ok": True, "message": f"Sent to {printer_name}."}

    await ws.send(json.dumps(result))


async def ping_loop(ws) -> None:
    while True:
        await asyncio.sleep(PING_INTERVAL_SECONDS)
        await ws.send(json.dumps({"type": "ping"}))


async def run(config: dict) -> None:
    url = config["ws_url"].rstrip("/") + "/?" + urlencode({"agent_token": config["token"]})
    backoff = RECONNECT_MIN_SECONDS
    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations(cafile=certifi.where())

    while True:
        try:
            log.info("Connecting...")
            async with websockets.connect(url, ping_interval=None, ssl=ssl_context) as ws:
                log.info("Connected — waiting for print jobs.")
                backoff = RECONNECT_MIN_SECONDS
                pinger = asyncio.create_task(ping_loop(ws))
                try:
                    async for raw in ws:
                        try:
                            message = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if message.get("type") == "pong":
                            continue
                        if message.get("type") == "print_job":
                            asyncio.create_task(handle_print_job(ws, message))
                finally:
                    pinger.cancel()
        except (websockets.exceptions.WebSocketException, OSError) as exc:
            log.warning("Connection lost (%s) — retrying in %ss", exc, backoff)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Unexpected error — retrying in %ss", backoff)

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, RECONNECT_MAX_SECONDS)


def default_config_dir() -> Path:
    """
    Directory to look for agent-config.json in by default.

    When running as a PyInstaller --onefile executable, `__file__` points
    into the temporary extraction folder (e.g. `...\\Temp\\_MEI123456\\`),
    NOT the folder the .exe actually sits in on disk — using it here would
    silently look for the config in the wrong place every single run.
    `sys.executable` is the actual .exe path in a frozen build; fall back to
    `__file__` when running the script directly (`python agent.py`), where
    sys.executable is the Python interpreter itself, not this script.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--config", type=Path,
        default=default_config_dir() / "agent-config.json",
        help="Path to agent-config.json (default: next to the .exe / this script).",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    log.info("Starting AIMS print agent for tenant %s", config["tenant_id"])
    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        log.info("Stopped.")


if __name__ == "__main__":
    main()

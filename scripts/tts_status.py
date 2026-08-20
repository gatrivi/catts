"""Cheap live status for CATTS TTS queue and local model workers."""
from __future__ import annotations

import json
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
WQ = ROOT / "data" / "workqueue"
STALE = 600


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def endpoint(url: str) -> bool:
    try:
        with urlopen(url, timeout=1) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def process_lines() -> list[str]:
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Select-Object -ExpandProperty CommandLine"],
            text=True, stderr=subprocess.DEVNULL, timeout=3,
        )
        return [line.lower() for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def main() -> int:
    state = read_json(WQ / "state.json")
    heartbeat = read_json(WQ / "heartbeat.json")
    now = time.time()
    hb_age = now - float(heartbeat.get("ts") or 0)
    lines = process_lines()
    fish_process = any(("api_server.py" in line) and ("8080" in line) for line in lines) or port_open(8080)
    api = endpoint("http://127.0.0.1:59200/health")
    bonsai_port = int(__import__("os").getenv("BONSAI_PORT", "9099"))
    bonsai = endpoint(f"http://127.0.0.1:{bonsai_port}/v1/models")
    current = state.get("current") or "-"
    meta = (state.get("jobs") or {}).get(current) or {}
    state_running = meta.get("status") == "running"
    queue = "RUNNING" if state_running and fish_process and hb_age <= STALE else ("STALE/STOPPED" if state_running else "IDLE")
    print(f"CATTS  api={'UP' if api else 'DOWN'}  fish={'UP' if fish_process else 'DOWN'}  bonsai={'UP' if bonsai else 'DOWN'}")
    print(f"QUEUE  {queue}  current={current}  heartbeat_age={int(hb_age) if hb_age < 999999 else 'unknown'}s")
    if heartbeat:
        print(f"WORK   keep={heartbeat.get('keep','-')} chapter={heartbeat.get('chapter','-')} chunk={heartbeat.get('chunk','-')}/{heartbeat.get('chunks','-')}")
    if queue == "STALE/STOPPED":
        print("WARN   state says running, but live worker/heartbeat evidence is missing")
    if not api and not bonsai and not fish_process:
        print("WARN   no TTS/model worker is running")
    return 0 if queue != "STALE/STOPPED" else 2


if __name__ == "__main__":
    raise SystemExit(main())



"""Run every offline example and drill once and save the console output.

    python scripts/capture_outputs.py

Writes one text file per command into outputs/. Nothing here needs an API key.
The MCP example is run with the finance evidence server started as a child
process on port 8765, and the unavailable-server drill is run after that
process has been stopped, so each output shows the situation it describes.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PORT = 8765

OFFLINE: dict[str, list[str]] = {
    "intent_tools": [sys.executable, "-m", "examples.intent_tools"],
    "run_context": [sys.executable, "-m", "examples.run_context"],
    "preview_execute": [sys.executable, "-m", "examples.preview_execute"],
    "resume_from_string": [sys.executable, "-m", "examples.resume_from_string"],
    "drill_retry": [sys.executable, "-m", "drills.retry_after_timeout"],
    "drill_reject": [sys.executable, "-m", "drills.reject_approval"],
    "audit_prep": [sys.executable, "-m", "audit_prep.main"],
}
WITH_SERVER = {"mcp_connect": [sys.executable, "-m", "examples.mcp_connect"]}
WITHOUT_SERVER = {"drill_unavailable": [sys.executable, "-m", "drills.unavailable_mcp_server"]}


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def capture(name: str, command: list[str]) -> None:
    print(f"running {name} ...", flush=True)
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    body = completed.stdout
    if completed.returncode != 0:
        body += f"\n[exit {completed.returncode}]\n{completed.stderr}"
    (OUT / f"{name}.txt").write_text(body)


def start_server() -> subprocess.Popen:
    server = subprocess.Popen(
        [sys.executable, "mcp_servers/finance_evidence_server.py"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if port_open(PORT):
            return server
        time.sleep(0.2)
    server.terminate()
    sys.exit(f"the finance evidence server did not start listening on port {PORT}")


def stop_server(server: subprocess.Popen) -> None:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
    deadline = time.monotonic() + 5
    while port_open(PORT) and time.monotonic() < deadline:
        time.sleep(0.1)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    if port_open(PORT):
        sys.exit(f"something is already listening on port {PORT}; stop it and rerun")
    for name, command in OFFLINE.items():
        capture(name, command)
    server = start_server()
    try:
        for name, command in WITH_SERVER.items():
            capture(name, command)
    finally:
        stop_server(server)
    for name, command in WITHOUT_SERVER.items():
        capture(name, command)
    print(f"done, outputs in {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()

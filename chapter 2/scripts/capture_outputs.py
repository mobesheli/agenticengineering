"""Run every live example once and save the console output for the manuscript.

    python scripts/capture_outputs.py

Writes one text file per example into outputs/. Requires OPENAI_API_KEY.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

COMMANDS: dict[str, list[str]] = {
    "describe": [sys.executable, "main.py", "describe"],
    "first_agent": [sys.executable, "-m", "examples.first_agent"],
    "first_agent_async": [sys.executable, "-m", "examples.first_agent_async"],
    "structured_output": [sys.executable, "-m", "examples.structured_output"],
    "tool_using_agent": [sys.executable, "-m", "examples.tool_using_agent"],
    "streaming": [sys.executable, "-m", "examples.streaming"],
    "guardrails": [sys.executable, "-m", "examples.guardrails"],
    "handoffs": [sys.executable, "-m", "examples.handoffs"],
    "tracing": [sys.executable, "-m", "examples.tracing"],
    "pipeline_CLM-4821": [sys.executable, "main.py", "run", "--claim", "CLM-4821"],
    "pipeline_CLM-4822": [sys.executable, "main.py", "run", "--claim", "CLM-4822"],
    "pipeline_CLM-4823": [sys.executable, "main.py", "run", "--claim", "CLM-4823"],
    "pipeline_off_topic": [sys.executable, "main.py", "run", "--off-topic"],
}


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set.")
    OUT.mkdir(exist_ok=True)
    for name, command in COMMANDS.items():
        print(f"running {name} ...", flush=True)
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, check=False
        )
        body = completed.stdout
        if completed.returncode != 0:
            body += f"\n[exit {completed.returncode}]\n{completed.stderr}"
        (OUT / f"{name}.txt").write_text(body)
    print(f"done, outputs in {OUT}")


if __name__ == "__main__":
    main()

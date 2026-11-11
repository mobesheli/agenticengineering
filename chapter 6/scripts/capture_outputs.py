"""Run every example and drill and save what each one printed.

    python scripts/capture_outputs.py

The chapter's console blocks are pasted from the files this writes to outputs/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "show_card": "examples.show_card",
    "quote_roundtrip": "examples.quote_roundtrip",
    "drill_hostile": "drills.hostile_request",
    "drill_untrusted_card": "drills.untrusted_card",
    "drill_parked": "drills.parked_task",
    "drill_retry": "drills.retry_same_message",
    "drill_supplier_down": "drills.supplier_down",
    "drill_silence": "drills.three_day_silence",
    "sourcing_run": "drills.sourcing_run",
}


def main() -> None:
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    for key, module in RUNS.items():
        done = subprocess.run(
            [sys.executable, "-m", module],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        (out / f"{key}.txt").write_text(done.stdout)
        print(
            f"{key:<22} {len(done.stdout.splitlines()):>3} lines  stderr={len(done.stderr)} bytes"
        )


if __name__ == "__main__":
    main()

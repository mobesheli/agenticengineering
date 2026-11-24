"""Build the security evidence pack from what the other examples produce.

python -m examples.evidence_pack
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from agents import set_tracing_disabled

from chapter8.evidence import build_pack
from chapter8.redaction import find_canaries
from examples.reconcile import run as reconcile
from examples.redaction_demo import CANARIES
from examples.redaction_demo import run as redaction


async def run(out: Path) -> list[str]:
    destinations = await redaction()
    report = {
        name: f"{len(find_canaries(payload, CANARIES))} of {len(CANARIES)} canaries"
        for name, payload in destinations.items()
    }
    set_tracing_disabled(True)
    harness = await reconcile(live=False, show=False)
    return build_pack(harness, report, out)


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        lines = asyncio.run(run(Path(folder)))
    print("evidence pack, built 2027-03-02")
    for line in lines:
        print(f"  {line}")


if __name__ == "__main__":
    main()

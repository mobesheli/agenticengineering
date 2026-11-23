"""Write the evidence pack for the baseline run and list what it contains.

python -m examples.evidence_pack
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from chapter7.evidence import build_artifacts, emit_evidence_pack
from examples.suite_run import run_profile

ONLINE_SAMPLE = {
    "period": "illustrative",
    "sampled_reviews": 200,
    "passed_code_checks": 194,
}
LIMITATIONS = [
    {
        "task": "je-split-02",
        "limit": "Misses some split entries.",
        "control": "Human review",
    },
    {
        "task": "je-clarify-03",
        "limit": "Sometimes decides first.",
        "control": "Blocked by gate",
    },
]


async def main(out_dir: Path | None = None) -> list[Path]:
    run = await run_profile("baseline")
    artifacts = build_artifacts(run, ONLINE_SAMPLE, LIMITATIONS)
    folder = out_dir or Path(tempfile.mkdtemp())
    written = emit_evidence_pack(run, artifacts, folder)
    for path in written:
        print(path.name)
    print("index.json")
    print()
    print(written[0].read_text())
    return written


if __name__ == "__main__":
    asyncio.run(main())

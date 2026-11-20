"""Crash a pipeline at its second step, then resume it from the checkpoint.

python -m examples.crash_and_resume
"""

import asyncio
import tempfile
from pathlib import Path

from chapter5.recovery import Checkpoints, Step, run_pipeline

HOLDS: dict[str, str] = {}
CRASHED = {"yet": False}


async def gather_records(done: dict, key: str) -> str:
    print("  gather_records ran")
    return "42 transactions"


async def place_hold(done: dict, key: str) -> str:
    HOLDS.setdefault(key, "hold on account 9411")
    print(f"  place_hold ran under key {key}; holds on file: {len(HOLDS)}")
    if not CRASHED["yet"]:
        CRASHED["yet"] = True
        raise ConnectionError("worker restarted before the checkpoint was saved")
    return HOLDS[key]


async def write_summary(done: dict, key: str) -> str:
    print("  write_summary ran")
    return f"summary of {done['gather_records']} with {done['place_hold']}"


STEPS = [
    Step("gather_records", gather_records),
    Step("place_hold", place_hold),
    Step("write_summary", write_summary),
]


async def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = str(Path(folder) / "checkpoints.db")
        print("first worker")
        try:
            await run_pipeline("run-7", STEPS, Checkpoints(path))
        except ConnectionError as crash:
            print(f"  crashed: {crash}")
        print("second worker")
        done = await run_pipeline("run-7", STEPS, Checkpoints(path))
        print(f"finished: {done['write_summary']}")


if __name__ == "__main__":
    asyncio.run(main())

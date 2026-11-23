"""Measure the judge against reference labels before trusting its verdicts.

python -m examples.judge_calibration          (recorded judge verdicts)
python -m examples.judge_calibration --live   (the real judge, needs a key)
"""

from __future__ import annotations

import asyncio
import json
import sys

from chapter7.judge import CalibrationReport, calibrate, grade_groundedness
from chapter7.tasks import DATA

ITEMS = json.loads((DATA / "calibration.json").read_text())


async def judge_verdicts(live: bool) -> list[bool]:
    """True means the judge called the rationale ungrounded."""
    if not live:
        return [item["judge"] == "ungrounded" for item in ITEMS]
    grounded = await asyncio.gather(
        *[
            grade_groundedness(item["rationale"], item["cited_clauses"])
            for item in ITEMS
        ]
    )
    return [not verdict for verdict in grounded]


async def main(live: bool = False) -> CalibrationReport:
    labels = [item["label"] == "ungrounded" for item in ITEMS]
    verdicts = await judge_verdicts(live)
    result = calibrate(labels, verdicts)
    print(f"{result.sample_size} rationales, {sum(labels)} labeled ungrounded")
    print(f"raw agreement  {result.agreement:.0%}")
    print(f"precision      {result.precision:.0%}")
    print(f"recall         {result.recall:.0%}")
    print(f"Cohen's kappa  {result.kappa:.2f}")
    for item, label, verdict in zip(ITEMS, labels, verdicts, strict=True):
        if label != verdict:
            kind = "judge flagged a grounded rationale" if verdict else "judge missed"
            print(f"  {item['item_id']}: {kind}")
    return result


if __name__ == "__main__":
    asyncio.run(main(live="--live" in sys.argv))

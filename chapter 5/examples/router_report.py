"""Score the request router against labels a reviewer assigned.

python -m examples.router_report            # recorded decisions, no key needed
python -m examples.router_report --live     # ask the real router, needs OPENAI_API_KEY
"""

import asyncio
import json
import sys
from pathlib import Path

from agents import Runner

from chapter5.router import request_router
from chapter5.router_eval import Scored, precision_recall, threshold_report

SAMPLE = json.loads(
    (Path(__file__).parent.parent / "data" / "router_sample.json").read_text()
)


async def decide_live() -> list[Scored]:
    scored = []
    for item in SAMPLE:
        run = await Runner.run(request_router, item["request"], max_turns=1)
        decision = run.final_output
        scored.append(Scored(item["label"], decision.category, decision.confidence))
    return scored


def report(sample: list[Scored]) -> list[str]:
    lines = [
        f"{len(sample)} labeled requests",
        "",
        "category           precision  recall",
    ]
    for category in ("balance_inquiry", "dispute", "fraud_report", "other"):
        precision, recall = precision_recall(sample, category)
        lines.append(f"{category:18} {precision:9.2f} {recall:7.2f}")
    lines += ["", "threshold  to a person  misrouted"]
    for row in threshold_report(sample, [0.50, 0.70, 0.90, 0.99]):
        lines.append(
            f"{row['threshold']:9.2f} {row['to_human']:11.0%} {row['misrouted']:10.0%}"
        )
    return lines


if __name__ == "__main__":
    if "--live" in sys.argv:
        decisions = asyncio.run(decide_live())
    else:
        decisions = [
            Scored(i["label"], i["predicted"], i["confidence"]) for i in SAMPLE
        ]
    print("\n".join(report(decisions)))

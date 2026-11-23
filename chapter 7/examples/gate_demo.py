"""The gate, shown three candidates. Runs on scripted replies.

python -m examples.gate_demo
"""

from __future__ import annotations

import asyncio
import math

from chapter7.gates import gate
from chapter7.metrics import paired_drop
from examples.suite_run import run_profile

CANDIDATES = {
    "unsafe": "follows one embedded instruction",
    "short_prompt": "loses four golden tasks",
    "thorough": "same quality, more steps",
}


async def main() -> dict:
    baseline = await run_profile("baseline")
    mean = baseline.golden_score[0]
    print(f"baseline: pass^4 {mean:.1%}, cost per review ${baseline.cost_per_task:.4f}")
    verdicts = {}
    for name in CANDIDATES:
        candidate = await run_profile(name)
        verdict = gate(baseline, candidate)
        verdicts[name] = verdict
        print(f"{name:13} {verdict.status.upper():6} {verdict.reason}".rstrip())
    short = await run_profile("short_prompt")
    drop, paired_error = paired_drop(baseline.golden, short.golden)
    unpaired = math.hypot(baseline.golden_score[1], short.golden_score[1])
    print("short_prompt, the same drop judged two ways:")
    print(f"  as two separate runs: drop {drop:.1%}, margin {1.96 * unpaired:.1%}")
    print(f"  paired by task:       drop {drop:.1%}, margin {1.96 * paired_error:.1%}")
    return verdicts


if __name__ == "__main__":
    asyncio.run(main())

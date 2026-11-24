"""Run the release pipeline on two attempts at one release, in each gate mode.

python -m examples.pipeline_run
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from chapter10.bundle import TEMPLATE
from chapter10.pipeline import render, run_pipeline


def main() -> list[str]:
    lines = ["first attempt at 41.3: a prompt change"]
    for mode in ("monitor", "comment", "block"):
        report = run_pipeline(TEMPLATE, mode, candidate="evals/attempt-1.json")
        gate = report.stages[-1].detail
        lines.append(f"  {mode:9}exit {report.exit_code}  {gate}")

    with tempfile.TemporaryDirectory() as folder:
        leaky = Path(folder) / "repo"
        shutil.copytree(TEMPLATE, leaky)
        (leaky / "config.env").write_text("PROVIDER_KEY=" + "sk-" + "a1B2" * 6 + "\n")
        report = run_pipeline(leaky, "monitor")
        lines.append("a key committed by mistake, with the gate still in monitor mode")
        lines.append(
            f"  monitor  exit {report.exit_code}  floor: {report.stages[0].detail}"
        )

        out = Path(folder) / "results"
        report = run_pipeline(TEMPLATE, "block", out=out)
        record = json.loads((out / "release-record.json").read_text())
        lines.append("second attempt at 41.3, in block mode")
        lines += render(report)
        digest = record["eval_report_sha256"][:12]
        lines.append(
            f"  record     verdict {record['verdict']}, report sha256 {digest}"
        )
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    main()

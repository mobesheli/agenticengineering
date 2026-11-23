"""Package one run's results as files a reviewer outside the team can open."""

from __future__ import annotations

import json
from pathlib import Path

from chapter7.metrics import SuiteResult

EVIDENCE_MAP = {
    "golden_suite_results": "does_it_do_the_job",
    "abuse_suite_results": "was_it_challenged",
    "online_sample_grades": "is_it_still_watched",
    "failure_analysis_log": "what_are_its_limits",
}


def emit_evidence_pack(
    run: SuiteResult, artifacts: dict[str, dict], out_dir: Path
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for artifact, question in EVIDENCE_MAP.items():
        path = out_dir / f"{question}__{artifact}.json"
        path.write_text(
            json.dumps({"run_id": run.run_id} | artifacts[artifact], indent=2)
        )
        written.append(path)
    index = dict(zip([path.name for path in written], EVIDENCE_MAP.values()))
    (out_dir / "index.json").write_text(json.dumps(index, indent=2))
    return written


def build_artifacts(
    run: SuiteResult, online_sample: dict, limitations: list[dict]
) -> dict:
    """The four artifacts, drawn from a suite result and two records kept by people."""
    mean, standard_error = run.golden_score
    return {
        "golden_suite_results": {
            "k": run.k,
            "tasks": len(run.golden),
            "pass_to_k": round(mean, 4),
            "standard_error": round(standard_error, 4),
            "failing_tasks": sorted(t for t, ok in run.golden.items() if not ok),
        },
        "abuse_suite_results": {
            "k": run.k,
            "failing_cases": sorted(run.abuse_failures),
        },
        "online_sample_grades": online_sample,
        "failure_analysis_log": {"known_limitations": limitations},
    }

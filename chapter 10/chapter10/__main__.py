"""Run the Chapter 10 release, listing, and platform-harness demonstrations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .artifacts import CHAPTER_ROOT, load_model
from .evidence import emit_deployment_evidence
from .gate import run_pipeline
from .intake import recommend_route
from .models import IntakeRequest
from .register import run_listing_demo


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Chapter 10 deployment harness."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/latest"))
    parser.add_argument(
        "--gate-mode", choices=("monitor", "comment", "block"), default="block"
    )
    parser.add_argument("--pipeline-only", action="store_true")
    parser.add_argument("--listing-demo", action="store_true")
    parser.add_argument("--intake", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.pipeline_only:
        report = run_pipeline(
            CHAPTER_ROOT / "template-repository",
            mode=args.gate_mode,
            output_path=args.output_dir / "pipeline-report.json",
        )
        print(report.model_dump_json(indent=2))
        raise SystemExit(0 if report.passed else 1)
    if args.listing_demo:
        refused, accepted = run_listing_demo(args.output_dir)
        print(
            json.dumps(
                {
                    "first_attempt": refused.model_dump(mode="json"),
                    "after_evidence": accepted.model_dump(mode="json"),
                },
                indent=2,
            )
        )
        raise SystemExit(0 if accepted.accepted else 1)
    if args.intake:
        request = load_model(args.intake, IntakeRequest)
        print(recommend_route(request).model_dump_json(indent=2))
        return
    summary = emit_deployment_evidence(args.output_dir, mode=args.gate_mode)
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["pipeline_passed"] else 1)


if __name__ == "__main__":
    main()

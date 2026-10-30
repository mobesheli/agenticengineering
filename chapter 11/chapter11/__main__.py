"""Run the year replay or write the complete Chapter 11 evidence pack."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from .board import replay
from .evidence import emit_evidence
from .memory import offline_merge


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Chapter 11 operations companion."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/latest"))
    parser.add_argument(
        "--day", type=int, default=365, choices=range(366), metavar="0..365"
    )
    parser.add_argument(
        "--replay-only",
        action="store_true",
        help="print the selected day's state without writing files",
    )
    parser.add_argument(
        "--live-memory",
        action="store_true",
        help="use the SDK for synthetic duplicate consolidation; makes paid model calls",
    )
    parser.add_argument("--model", help="explicit model for --live-memory")
    args = parser.parse_args()
    if args.replay_only:
        if args.live_memory or args.model:
            parser.error("live memory options do not apply to --replay-only")
        print(json.dumps(replay(args.day), indent=2))
        return
    merge = offline_merge
    if args.live_memory:
        if not args.model or not os.environ.get("OPENAI_API_KEY"):
            parser.error(
                "--live-memory requires --model and OPENAI_API_KEY in the environment"
            )
        from .live import sdk_merger

        merge = sdk_merger(args.model)
    elif args.model:
        parser.error("--model requires --live-memory")
    try:
        summary = asyncio.run(emit_evidence(args.output_dir, day=args.day, merge=merge))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"chapter11: {exc}\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

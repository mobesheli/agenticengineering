from __future__ import annotations

import argparse
import asyncio
import json
import os

from openai import APIError, AuthenticationError, PermissionDeniedError, RateLimitError

from claims_pipeline.agents import (
    DEFAULT_MODEL,
    build_claims_intake_agent,
    build_claims_reviewer_agent,
    build_router_agent,
)
from claims_pipeline.data import list_claim_ids
from claims_pipeline.pipeline import run_live_pipeline, run_offline_pipeline


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2))


def _handle_list_claims() -> None:
    _print_json({"available_claims": list_claim_ids()})


def _handle_describe(model: str) -> None:
    intake = build_claims_intake_agent(model=model)
    reviewer = build_claims_reviewer_agent(model=model)
    router = build_router_agent(model=model)
    payload = {
        "model": model,
        "agents": [
            {
                "name": intake.name,
                "tools": [tool.name for tool in intake.tools],
                "input_guardrails": [guardrail.name for guardrail in intake.input_guardrails],
                "output_type": intake.output_type.__name__,
            },
            {
                "name": reviewer.name,
                "tools": [tool.name for tool in reviewer.tools],
                "output_guardrails": [
                    guardrail.name for guardrail in reviewer.output_guardrails
                ],
                "output_type": reviewer.output_type.__name__,
            },
            {
                "name": router.name,
                "handoffs": [agent.name for agent in router.handoffs],
            },
        ],
    }
    _print_json(payload)


def _handle_offline(claim_id: str) -> None:
    result = run_offline_pipeline(claim_id)
    _print_json(result.model_dump())


def _handle_live(claim_id: str, model: str) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is required for the live SDK run. "
            "Use `python main.py offline --claim ...` for the local demo."
        )
    try:
        result = asyncio.run(run_live_pipeline(claim_id=claim_id, model=model))
    except AuthenticationError as exc:
        raise SystemExit(
            "OpenAI authentication failed. Check that the API key is valid."
        ) from exc
    except PermissionDeniedError as exc:
        raise SystemExit(
            "The API key is valid, but this account does not have permission to use "
            "the requested model or API."
        ) from exc
    except RateLimitError as exc:
        raise SystemExit(
            "The API key was accepted, but the live run was blocked by quota or rate limits. "
            "Check billing, credits, and usage limits for the OpenAI project."
        ) from exc
    except APIError as exc:
        raise SystemExit(f"OpenAI returned an API error during the live run: {exc}") from exc
    _print_json(result.model_dump())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Chapter 2 claims pipeline companion project. "
            "Start with `describe`, then run the `offline` claim examples before using `live`."
        ),
        epilog=(
            "Examples:\n"
            "  python main.py describe\n"
            "  python main.py offline --claim CLM-1001\n"
            "  python main.py live --claim CLM-1001"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model name used for live SDK runs and agent descriptions.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-claims",
        help="Show the sample claim ids.",
        description="Print the built-in sample claim ids used throughout the chapter.",
    )
    subparsers.add_parser(
        "describe",
        help="Show the agent, tool, and handoff setup.",
        description="Print the app structure: agents, tools, guardrails, and handoffs.",
    )

    offline = subparsers.add_parser(
        "offline",
        help="Run the deterministic local demo.",
        description=(
            "Run the local learning path without calling the OpenAI API. "
            "This is the recommended first run for the chapter."
        ),
    )
    offline.add_argument(
        "--claim",
        required=True,
        help="Sample claim id: CLM-1001, CLM-1002, or CLM-1003.",
    )

    live = subparsers.add_parser(
        "live",
        help="Run the live OpenAI Agents SDK pipeline.",
        description=(
            "Run the same claims workflow with real OpenAI model calls. "
            "Requires OPENAI_API_KEY."
        ),
    )
    live.add_argument(
        "--claim",
        required=True,
        help="Sample claim id: CLM-1001, CLM-1002, or CLM-1003.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list-claims":
        _handle_list_claims()
        return

    if args.command == "describe":
        _handle_describe(model=args.model)
        return

    if args.command == "offline":
        _handle_offline(claim_id=args.claim)
        return

    if args.command == "live":
        _handle_live(claim_id=args.claim, model=args.model)
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()

"""Command-line entry point for the Chapter 2 claims pipeline.

    python main.py describe
    python main.py list-claims
    python main.py run --claim CLM-4821
    python main.py run --off-topic
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from openai import APIError, AuthenticationError, RateLimitError

from claims_pipeline.agents import (
    claims_reviewer,
    escalation_agent,
    intake_agent,
    policy_advisor,
    triage_agent,
)
from claims_pipeline.data import OFF_TOPIC_REQUEST, SAMPLE_CLAIMS
from claims_pipeline.models import Claim
from claims_pipeline.pipeline import process_claim
from claims_pipeline.settings import MODELS


def describe() -> None:
    for agent in (intake_agent, claims_reviewer, escalation_agent, policy_advisor, triage_agent):
        tools = [tool.name for tool in agent.tools] or ["(none)"]
        guards = [g.name for g in agent.input_guardrails] + [
            g.name for g in agent.output_guardrails
        ]
        output = getattr(agent.output_type, "__name__", "str")
        handoffs = [getattr(h, "name", "?") for h in agent.handoffs] or ["(none)"]
        print(f"{agent.name:18} model={agent.model}")
        print(f"{'':18} tools={', '.join(tools)}")
        print(f"{'':18} guardrails={', '.join(guards) or '(none)'}")
        print(f"{'':18} output_type={output} handoffs={', '.join(handoffs)}")
    print(f"registry: fast={MODELS.fast} review={MODELS.review}")


def list_claims() -> None:
    for claim in SAMPLE_CLAIMS.values():
        print(f"{claim.claim_id}  {claim.claim_type:9} ${claim.amount_usd:>10,.2f}  {claim.description[:60]}")


def run(claim: Claim) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Export it and run again.")
    try:
        outcome = asyncio.run(process_claim(claim))
    except AuthenticationError:
        sys.exit("OpenAI rejected the API key. Check OPENAI_API_KEY.")
    except RateLimitError:
        sys.exit("The request was blocked by quota or rate limits. Check billing for the project.")
    except APIError as exc:
        sys.exit(f"OpenAI returned an API error: {exc}")
    print(outcome.model_dump_json(indent=2, exclude_none=True))


def off_topic_claim() -> Claim:
    return Claim(
        claim_id="REQ-0000",
        policy_number="XX-0000000",
        policyholder_id="PH-00000",
        claim_type="property",
        amount_usd=1.0,
        date_of_loss="2026-01-01",
        submitted_documents=[],
        description="A raw submission that is not a claim.",
        raw_submission=OFF_TOPIC_REQUEST,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chapter 2 claims pipeline.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("describe", help="Print the agents, tools, and guardrails. No API calls.")
    commands.add_parser("list-claims", help="Print the sample claims.")
    runner = commands.add_parser("run", help="Run the pipeline against the API.")
    group = runner.add_mutually_exclusive_group(required=True)
    group.add_argument("--claim", choices=sorted(SAMPLE_CLAIMS), help="A sample claim id.")
    group.add_argument("--off-topic", action="store_true", help="Send a non-insurance request.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "describe":
        describe()
    elif args.command == "list-claims":
        list_claims()
    elif args.command == "run":
        claim = off_topic_claim() if args.off_topic else SAMPLE_CLAIMS[args.claim]
        run(claim)


if __name__ == "__main__":
    main()

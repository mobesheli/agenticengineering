"""Reflection: one agent drafts, another checks, and the loop has a hard limit."""

from __future__ import annotations

from agents import Agent, Runner
from pydantic import BaseModel

from chapter5.models import MODELS, QUICK

WRITER_GUIDE = """Write a short case narrative for an analyst: what happened, in
date order, in plain sentences. Put the record identifier in square brackets
after every factual statement. State no fact that is not in the case records."""

REVIEWER_GUIDE = """You check a case narrative against the case records.
List every statement that has no record identifier, cites a record that does
not exist, or says something the cited record does not say. Set acceptable to
true only when the list is empty. Do not rewrite the narrative."""


class Review(BaseModel):
    acceptable: bool
    problems: list[str]


class Narrative(BaseModel):
    text: str
    passed_review: bool
    revisions: int


narrative_writer = Agent(
    name="narrative_writer", model=MODELS.mid, instructions=WRITER_GUIDE
)
narrative_reviewer = Agent(
    name="narrative_reviewer",
    model=MODELS.small,
    model_settings=QUICK,
    instructions=REVIEWER_GUIDE,
    output_type=Review,
)


async def ask(agent: Agent, text: str):
    return (await Runner.run(agent, text, max_turns=1)).final_output


async def draft_with_review(records: str, max_revisions: int = 2) -> Narrative:
    draft = await ask(narrative_writer, records)
    for revision in range(max_revisions + 1):
        both = f"RECORDS\n{records}\n\nDRAFT\n{draft}"
        review = await ask(narrative_reviewer, both)
        if review.acceptable:
            return Narrative(text=draft, passed_review=True, revisions=revision)
        if revision == max_revisions:
            break
        fixes = "\n".join(review.problems)
        draft = await ask(narrative_writer, f"{both}\n\nFIX THESE\n{fixes}")
    return Narrative(text=draft, passed_review=False, revisions=max_revisions)

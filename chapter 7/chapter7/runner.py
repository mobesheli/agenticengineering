"""Running trials: one fresh environment, one agent run, one stored record each."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from agents import Agent, MaxTurnsExceeded, Runner, set_tracing_disabled
from agents.usage import Usage
from pydantic import BaseModel

from chapter7.environment import ReviewEnvironment, provision
from chapter7.models import cost_of
from chapter7.tasks import EvalTask

set_tracing_disabled(True)

TURN_CAP = 10
MakeAgent = Callable[[ReviewEnvironment], Agent]


class ToolCall(BaseModel):
    name: str
    arguments: str
    failed: bool = False


class Transcript(BaseModel):
    tool_calls: list[ToolCall]
    final_message: str
    hit_turn_cap: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


class Trial(BaseModel):
    task_id: str
    index: int
    transcript: Transcript
    final_state: dict[str, Any]
    seconds: float
    cost: float


def to_transcript(
    items: list, usage: Usage, final: Any, capped: bool = False
) -> Transcript:
    """Reduce the SDK's run items to the tool calls and whether each one failed."""
    outputs = {
        item.raw_item["call_id"]: str(item.output)
        for item in items
        if item.type == "tool_call_output_item"
    }
    calls = [
        ToolCall(
            name=item.raw_item.name,
            arguments=item.raw_item.arguments,
            failed=outputs.get(item.raw_item.call_id, "").startswith("error:"),
        )
        for item in items
        if item.type == "tool_call_item"
    ]
    return Transcript(
        tool_calls=calls,
        final_message=str(final or ""),
        hit_turn_cap=capped,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )


async def run_trial(make_agent: MakeAgent, task: EvalTask, index: int) -> Trial:
    env = provision(task, index)
    agent = make_agent(env)
    started = time.perf_counter()
    try:
        result = await Runner.run(agent, task.instruction, max_turns=TURN_CAP)
        usage = result.context_wrapper.usage
        transcript = to_transcript(result.new_items, usage, result.final_output)
    except MaxTurnsExceeded as stopped:
        data = stopped.run_data
        usage = data.context_wrapper.usage
        transcript = to_transcript(data.new_items, usage, None, capped=True)
    return Trial(
        task_id=task.task_id,
        index=index,
        transcript=transcript,
        final_state=env.snapshot(),
        seconds=time.perf_counter() - started,
        cost=cost_of("reviewer", usage.input_tokens, usage.output_tokens),
    )


async def run_suite(
    make_agent: MakeAgent, tasks: list[EvalTask], k: int
) -> list[Trial]:
    jobs = [run_trial(make_agent, task, i) for task in tasks for i in range(k)]
    return await asyncio.gather(*jobs)

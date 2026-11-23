"""Scripted stand-ins for the model, so everything runs without an API key.

The SDK runner, the tools, and the environment are real. Only the model's replies
are scripted. A profile is a reviewer with named flaws on named trials, which makes
every number the keyless examples print reproducible. The numbers are illustrative.
"""

from __future__ import annotations

from agents import Agent, Usage
from agents.testing import ScriptedModel, assistant_message, function_call

from chapter7.environment import ReviewEnvironment
from chapter7.reviewer import build_reviewer

USAGE_PER_TURN = Usage(
    requests=1, input_tokens=1400, output_tokens=110, total_tokens=1510
)

BASELINE = {"je-split-02": {2: "wrong_verdict"}, "je-clarify-03": {1: "skip_policy"}}
SHORT_PROMPT = BASELINE | {
    "je-no-document-01": {0: "wrong_verdict", 3: "wrong_verdict"},
    "je-no-document-02": {1: "wrong_verdict"},
    "je-duplicate-02": {2: "wrong_verdict"},
    "je-backdate-02": {0: "wrong_verdict"},
}
UNSAFE = BASELINE | {"abuse-hijack-01": {3: "follow_injection"}}
PROFILES = {
    "baseline": BASELINE,
    "short_prompt": SHORT_PROMPT,
    "unsafe": UNSAFE,
    "thorough": BASELINE,
}


def script_for(env: ReviewEnvironment, profile: str) -> list[list]:
    """The model turns for one trial: tool calls in order, then a closing message."""
    task, flaw = (
        env.task,
        PROFILES[profile].get(env.task.task_id, {}).get(env.trial_index),
    )
    expected = task.expected
    verdict, route = expected["verdict"], expected["route"]
    if flaw in ("wrong_verdict", "follow_injection"):
        verdict, route = "approve", "none"
    names = [] if flaw == "skip_policy" else ["lookup_policy"]
    names += ["get_entry", "get_supporting_documents"]
    if env.entry.get("flaky_documents"):
        names.append("get_supporting_documents")
    if env.history or profile == "thorough":
        names.append("get_case_history")
    if profile == "thorough":
        names.append("get_entry")
    if flaw == "follow_injection":
        names.append("post_entry")
    record = {
        "verdict": verdict,
        "route": route,
        "rationale": f"{task.reference_solution} Policy clause {expected['clause']} applies.",
        "cited_clauses": [expected["clause"]],
    }
    turns = [
        [function_call(name, {}, call_id=f"call_{n}")] for n, name in enumerate(names)
    ]
    turns.append([function_call("record_verdict", record, call_id="call_verdict")])
    turns.append([assistant_message(f"Recorded: {verdict}.")])
    return turns


def scripted_reviewer(profile: str):
    """An agent factory whose reviewers replay the given profile."""

    def make_agent(env: ReviewEnvironment) -> Agent:
        model = ScriptedModel(script_for(env, profile), default_usage=USAGE_PER_TURN)
        return build_reviewer(env).clone(model=model)

    return make_agent

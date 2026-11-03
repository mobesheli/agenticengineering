import re
from pathlib import Path

from agents import FunctionTool
from agents.tracing import gen_trace_id

from claims_pipeline import agents as agents_module
from claims_pipeline.agents import (
    claims_reviewer,
    escalation_agent,
    intake_agent,
    policy_advisor,
    triage_agent,
)
from claims_pipeline.settings import MODELS, TOOL_TIMEOUT_SECONDS
from claims_pipeline.tools import check_required_documents, get_claim_history, lookup_policy

PACKAGE_DIR = Path(agents_module.__file__).resolve().parent


def test_guardrails_are_attached_to_the_pipeline_agents():
    assert [g.name for g in intake_agent.input_guardrails] == ["reject_non_insurance"]
    assert intake_agent.input_guardrails[0].run_in_parallel is False
    assert [g.name for g in claims_reviewer.output_guardrails] == ["enforce_citations"]


def test_network_tools_are_async_with_a_timeout():
    for tool in (lookup_policy, get_claim_history):
        assert isinstance(tool, FunctionTool)
        assert tool.timeout_seconds == TOOL_TIMEOUT_SECONDS
        assert tool.timeout_behavior == "error_as_result"
    assert check_required_documents.timeout_seconds is None


def test_reviewer_has_both_tools_and_structured_output():
    assert {tool.name for tool in claims_reviewer.tools} == {"lookup_policy", "get_claim_history"}
    assert claims_reviewer.output_type.__name__ == "ClaimVerdict"


def test_triage_handoff_targets_are_defined():
    names = {getattr(target, "name", None) for target in triage_agent.handoffs}
    assert names == {"claims_reviewer", "policy_advisor"}
    assert policy_advisor.tools[0].name == "lookup_policy"


def test_trace_ids_follow_the_sdk_format():
    assert re.fullmatch(r"trace_[0-9a-f]{32}", gen_trace_id())


def test_no_model_name_is_hard_coded_outside_the_registry():
    offenders = []
    for path in PACKAGE_DIR.glob("*.py"):
        if path.name == "settings.py":
            continue
        if re.search(r'"gpt-', path.read_text()):
            offenders.append(path.name)
    assert offenders == []
    assert {intake_agent.model, escalation_agent.model, claims_reviewer.model} <= {
        MODELS.fast,
        MODELS.review,
    }

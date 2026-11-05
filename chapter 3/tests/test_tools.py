"""Schemas, context-carried values, and the error shape."""

import json

from agents import Agent, Runner
from agents.testing import assistant_message, function_call

from ch3.deps import RunDeps, derive_idempotency_key
from ch3.erp_tools import ERP_TOOLS, erp
from ch3.errors import RATE_LIMITED_EXAMPLE, tool_error
from ch3.previews import build_preview, content_hash, execute_previewed_refund, preview_refund
from ch3.refund_tools import RefundRequest, RefundResult, execute_refund, issue_refund
from tests.conftest import refund_fields, scripted, tool_call_then_message


def test_context_parameter_is_excluded_from_every_model_facing_schema():
    for tool in ERP_TOOLS + [issue_refund, execute_refund, execute_previewed_refund]:
        schema = json.dumps(tool.params_json_schema)
        assert "idempotency_key" not in schema, tool.name
        assert "actor_id" not in schema, tool.name
        assert "ctx" not in tool.params_json_schema["properties"], tool.name


def test_erp_tools_are_named_by_intent_and_reason_code_is_constrained():
    assert [tool.name for tool in ERP_TOOLS] == [
        "preview_po_change", "submit_po_change_for_approval", "get_po_change_status",
    ]
    proposal = ERP_TOOLS[0].params_json_schema["$defs"]["POChangeProposal"]
    assert proposal["properties"]["reason_code"]["enum"] == [
        "price_correction", "vendor_change", "cancel_line",
    ]
    assert set(proposal["required"]) == {"po_number", "line_item", "new_quantity", "reason_code"}


async def test_submit_po_change_reads_the_key_from_the_run_context():
    model = scripted(
        [function_call("submit_po_change_for_approval",
                       {"proposal": {"po_number": "PO-10021", "line_item": 1,
                                     "new_quantity": 35, "reason_code": "price_correction"}},
                       call_id="call_1")],
        [function_call("submit_po_change_for_approval",
                       {"proposal": {"po_number": "PO-10021", "line_item": 1,
                                     "new_quantity": 35, "reason_code": "price_correction"}},
                       call_id="call_2")],
        [assistant_message("submitted")],
    )
    agent = Agent(name="po", instructions="x", tools=ERP_TOOLS, model=model)
    deps = RunDeps(idempotency_key="po-key-1", actor_id="buyer@example.com")
    result = await Runner.run(agent, "change line 1", context=deps)
    outputs = [i.output for i in result.new_items if i.type == "tool_call_output_item"]
    assert outputs[0]["replayed"] is False
    assert outputs[1]["replayed"] is True
    assert outputs[0]["approval_request_id"] == outputs[1]["approval_request_id"]
    assert erp.requests[outputs[0]["approval_request_id"]]["status"] == "pending"


async def test_issue_refund_takes_key_and_actor_from_context_not_from_the_model(deps):
    model = tool_call_then_message("issue_refund", {"req": refund_fields(amount_cents=4_500)})
    agent = Agent(name="refund", instructions="x", tools=[issue_refund], model=model)
    result = await Runner.run(agent, "refund", context=deps)
    call = next(i for i in result.new_items if i.type == "tool_call_item")
    output = next(i for i in result.new_items if i.type == "tool_call_output_item").output
    assert set(json.loads(call.raw_item.arguments)) == {"req"}
    assert isinstance(output, RefundResult)
    assert output.status == "issued" and output.amount_cents == 4_500
    assert len(model.calls[0].tools) == 1


def test_idempotency_key_is_stable_for_the_same_intent():
    a = derive_idempotency_key(run_id="r1", customer_id="c1", charge_id="ch1")
    b = derive_idempotency_key(run_id="r1", customer_id="c1", charge_id="ch1")
    c = derive_idempotency_key(run_id="r1", customer_id="c1", charge_id="ch2")
    assert a == b and a != c


def test_preview_hash_pins_the_exact_request_and_execute_refuses_a_stale_hash(deps):
    from ch3.previews import execute_previewed_refund_impl

    req = RefundRequest(**refund_fields(amount_cents=4_500))
    preview = build_preview(req)
    assert preview.content_hash == content_hash(req)
    changed = RefundRequest(**refund_fields(amount_cents=4_600))
    assert content_hash(changed) != preview.content_hash
    refused = execute_previewed_refund_impl(deps, changed, preview.content_hash)
    assert refused["ok"] is False and refused["error_class"] == "preview_mismatch"
    assert refused["retryable"] is False and refused["machine_action_hint"] == "replan"
    issued = execute_previewed_refund_impl(deps, req, preview.content_hash)
    assert isinstance(issued, RefundResult) and issued.status == "issued"


def test_preview_tool_has_no_side_effects(deps):
    from ch3 import payments

    assert preview_refund.params_json_schema["properties"].keys() == {"req"}
    build_preview(RefundRequest(**refund_fields()))
    assert payments.count_refunds() == 0


def test_error_shape_carries_all_three_audiences():
    for key in ("ok", "error_class", "retryable", "user_safe_message",
                "developer_detail", "machine_action_hint"):
        assert key in RATE_LIMITED_EXAMPLE
    assert RATE_LIMITED_EXAMPLE["ok"] is False
    built = tool_error("not_found", retryable=False, user_safe_message="No such record.",
                       developer_detail="404 from upstream", machine_action_hint="ask_user")
    assert "retry_after_seconds" not in built
    assert built["machine_action_hint"] == "ask_user"

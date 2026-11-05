"""Preview and execute: the safest write pattern in production.

``preview_refund`` returns the calculated effect and a content hash without
changing anything. ``execute_previewed_refund`` carries that hash and refuses to
run when the hash does not match the request it was given, so what gets
approved is what gets executed.
"""

from __future__ import annotations

import hashlib

from agents import RunContextWrapper, function_tool
from pydantic import BaseModel

from ch3.deps import RunDeps
from ch3.errors import ToolError, tool_error
from ch3.refund_tools import (
    RefundRequest,
    RefundResult,
    issue_refund_impl,
    needs_second_pair_of_eyes,
)


class RefundPreview(BaseModel):
    """The previewed effect of a refund, plus the hash that pins it."""

    customer_id: str
    original_charge_id: str
    amount_cents: int
    reason: str
    content_hash: str


def content_hash(req: RefundRequest) -> str:
    """Hash the validated request so an approval binds to one exact effect."""
    canonical = req.model_dump_json()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_preview(req: RefundRequest) -> RefundPreview:
    """Compute the preview for a request without touching the store."""
    return RefundPreview(**req.model_dump(), content_hash=content_hash(req))


@function_tool
def preview_refund(req: RefundRequest) -> RefundPreview:
    """Show what a refund would do without issuing it. Returns the previewed
    effect and a content_hash that execute_previewed_refund must carry.
    Safe to call as often as you like. No side effects."""
    return build_preview(req)


@function_tool(needs_approval=needs_second_pair_of_eyes)
def execute_previewed_refund(
    ctx: RunContextWrapper[RunDeps],
    customer_id: str,
    original_charge_id: str,
    amount_cents: int,
    reason: str,
    content_hash: str,
) -> RefundResult | ToolError:
    """Execute a refund exactly as previewed. Refused when content_hash does
    not match the request, in which case call preview_refund again."""
    req = RefundRequest(customer_id=customer_id, original_charge_id=original_charge_id,
                        amount_cents=amount_cents, reason=reason)
    return execute_previewed_refund_impl(ctx.context, req, content_hash)


def execute_previewed_refund_impl(
    deps: RunDeps, req: RefundRequest, presented_hash: str
) -> RefundResult | ToolError:
    """Verify the hash against the request, then issue through the idempotent path."""
    expected = content_hash(req)
    if presented_hash != expected:
        return tool_error(
            "preview_mismatch",
            retryable=False,
            user_safe_message="The refund details changed after they were previewed. "
                              "I need to preview them again before executing.",
            developer_detail=f"content_hash {presented_hash} does not match {expected}",
            machine_action_hint="replan",
        )
    return issue_refund_impl(deps, req)

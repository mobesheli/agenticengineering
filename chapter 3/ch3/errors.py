"""Error responses are part of the agent loop.

One error shape carries information for three audiences. The agent loop reads
``error_class``, ``retryable``, ``retry_after_seconds``, and
``machine_action_hint``. The end user sees ``user_safe_message``. The audit log
keeps ``developer_detail``.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

MachineActionHint = Literal[
    "backoff_then_retry",
    "replan",
    "ask_user",
    "escalate",
    "stop",
]


class ToolError(TypedDict):
    """The minimum acceptable error shape for a tool response."""

    ok: Literal[False]
    error_class: str
    retryable: bool
    retry_after_seconds: NotRequired[int]
    user_safe_message: str
    developer_detail: str
    machine_action_hint: str


RATE_LIMITED_EXAMPLE: ToolError = {
    "ok": False,
    "error_class": "rate_limited",
    "retryable": True,
    "retry_after_seconds": 30,
    "user_safe_message": "The vendor system is busy. I can try again "
                         "in about thirty seconds.",
    "developer_detail": "HTTP 429 from upstream; rate-limit-remaining=0",
    "machine_action_hint": "backoff_then_retry",
}


def tool_error(
    error_class: str,
    *,
    retryable: bool,
    user_safe_message: str,
    developer_detail: str,
    machine_action_hint: MachineActionHint,
    retry_after_seconds: int | None = None,
) -> ToolError:
    """Build an error response in the chapter's shape.

    Tools return this instead of raising, so the model reads a structured
    description of what happened and what it may do next.
    """
    error: ToolError = {
        "ok": False,
        "error_class": error_class,
        "retryable": retryable,
        "user_safe_message": user_safe_message,
        "developer_detail": developer_detail,
        "machine_action_hint": machine_action_hint,
    }
    if retry_after_seconds is not None:
        error["retry_after_seconds"] = retry_after_seconds
    return error

import sys
from pathlib import Path

import pytest
from agents import set_tracing_disabled
from agents.testing import ScriptedModel, assistant_message, function_call

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ch3 import payments  # noqa: E402
from ch3.deps import RunDeps  # noqa: E402

set_tracing_disabled(True)

REFUND_FIELDS = {
    "customer_id": "cus_8841",
    "original_charge_id": "ch_3f9a21",
    "amount_cents": 21_450,
    "reason": "Damaged on arrival",
}


@pytest.fixture(autouse=True)
def clean_store():
    payments.reset_store()
    payments.set_refund_id_source(None)
    yield
    payments.reset_store()


@pytest.fixture
def deps() -> RunDeps:
    return RunDeps(idempotency_key="key-test-0001", actor_id="tester@example.com")


def refund_fields(**overrides) -> dict:
    return {**REFUND_FIELDS, **overrides}


def scripted(*steps) -> ScriptedModel:
    return ScriptedModel(list(steps))


def tool_call_then_message(tool_name: str, arguments: dict, message: str = "done") -> ScriptedModel:
    return scripted(
        [function_call(tool_name, arguments, call_id="call_1")],
        [assistant_message(message)],
    )

import pytest
from agents import set_tracing_disabled

from chapter8.harness import Harness


@pytest.fixture(autouse=True)
def no_tracing():
    set_tracing_disabled(True)


@pytest.fixture
def harness() -> Harness:
    return Harness.build()

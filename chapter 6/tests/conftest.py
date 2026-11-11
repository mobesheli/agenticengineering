from __future__ import annotations

import pytest

from chapter6.audit import audit_log
from chapter6.neighborhood import build_neighborhood


@pytest.fixture
async def hood():
    audit_log.clear()
    neighborhood = build_neighborhood()
    yield neighborhood
    await neighborhood.aclose()

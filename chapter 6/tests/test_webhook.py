from __future__ import annotations

import httpx

from chapter6.remote import Delegation, answer_supplier_question, request_supplier_quote
from chapter6.sample import BUYER, CASE, bracket_bom
from chapter6.webhook import TOKEN_HEADER, NotificationInbox, build_webhook

URL = "https://buyer.test/a2a/notifications/{}"


def status(task_id: str, state: str, stamp: str = "t1") -> dict:
    update = {"taskId": task_id, "status": {"state": state, "timestamp": stamp}}
    return {"statusUpdate": update}


async def post(inbox, sender, event, token):
    transport = httpx.ASGITransport(app=build_webhook(inbox))
    async with httpx.AsyncClient(transport=transport) as client:
        return await client.post(
            URL.format(sender), json=event, headers={TOKEN_HEADER: token}
        )


async def test_token_is_checked_before_anything_is_read():
    inbox = NotificationInbox(tokens={"nordbolt": "right"})
    inbox.expect("nordbolt", "task-1")
    refused = await post(
        inbox, "nordbolt", status("task-1", "TASK_STATE_COMPLETED"), "wrong"
    )
    unknown = await post(
        inbox, "stranger", status("task-1", "TASK_STATE_COMPLETED"), ""
    )
    assert refused.status_code == unknown.status_code == 401
    assert not inbox.work_queue


async def test_duplicates_are_acknowledged_and_ignored():
    inbox = NotificationInbox(tokens={"nordbolt": "right"})
    inbox.expect("nordbolt", "task-1")
    event = status("task-1", "TASK_STATE_COMPLETED")
    first = await post(inbox, "nordbolt", event, "right")
    second = await post(inbox, "nordbolt", event, "right")
    assert first.status_code == second.status_code == 204
    assert inbox.work_queue == [("nordbolt", "task-1", "TASK_STATE_COMPLETED")]


async def test_the_same_state_twice_is_two_events_when_the_timestamps_differ():
    inbox = NotificationInbox(tokens={"nordbolt": "right"})
    inbox.expect("nordbolt", "task-1")
    await post(inbox, "nordbolt", status("task-1", "TASK_STATE_WORKING", "t1"), "right")
    await post(inbox, "nordbolt", status("task-1", "TASK_STATE_WORKING", "t2"), "right")
    assert len(inbox.work_queue) == 2


async def test_early_notifications_are_held_until_the_task_is_known():
    inbox = NotificationInbox(tokens={"nordbolt": "right"})
    early = await post(
        inbox, "nordbolt", status("task-9", "TASK_STATE_WORKING"), "right"
    )
    assert early.status_code == 204 and not inbox.work_queue
    inbox.expect("nordbolt", "task-9")
    assert inbox.work_queue == [("nordbolt", "task-9", "TASK_STATE_WORKING")]
    assert not inbox.held


async def test_one_counterparty_cannot_report_on_another_counterpartys_task():
    inbox = NotificationInbox(tokens={"nordbolt": "n", "rivetridge": "r"})
    inbox.expect("nordbolt", "task-1")
    crossed = await post(
        inbox, "rivetridge", status("task-1", "TASK_STATE_FAILED"), "r"
    )
    assert crossed.status_code == 404 and not inbox.work_queue


async def test_real_server_notifies_the_webhook_when_a_parked_task_finishes(hood):
    via = Delegation(hood.http, BUYER, CASE)
    parked = await request_supplier_quote(
        via, "nordbolt", bracket_bom(drawing_rev=None)
    )
    hood.inbox.expect("nordbolt", parked.task_id)
    await answer_supplier_question(
        via, "nordbolt", parked.task_id, {"drawing_rev": "C"}
    )
    changes = [change for _, _, change in hood.inbox.work_queue]
    assert changes[-1] == "TASK_STATE_COMPLETED" and "artifact" in changes

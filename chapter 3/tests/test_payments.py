"""The idempotency guarantee lives in the database, under real concurrency."""

from concurrent.futures import ThreadPoolExecutor

from ch3 import payments


def write(key: str, amount: int = 21_450) -> payments.RefundRow:
    return payments.create_refund_atomic(
        idempotency_key=key,
        charge_id="ch_3f9a21",
        amount_cents=amount,
        actor_id="tester@example.com",
        reason="Damaged on arrival",
    )


def test_first_write_issues_and_second_replays_the_same_row():
    payments.set_refund_id_source(["rf_7f3a9c", "rf_000bad"])
    first = write("key-a")
    second = write("key-a")
    assert first == payments.RefundRow("rf_7f3a9c", 21_450, replayed=False)
    assert second == payments.RefundRow("rf_7f3a9c", 21_450, replayed=True)
    assert payments.count_refunds() == 1


def test_different_keys_are_different_refunds():
    write("key-a")
    write("key-b")
    assert payments.count_refunds() == 2


def test_concurrent_retries_with_one_key_produce_exactly_one_refund():
    workers = 16
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda _: write("key-race"), range(workers)))
    assert payments.count_refunds() == 1
    assert sum(1 for row in rows if not row.replayed) == 1
    assert len({row.refund_id for row in rows}) == 1


def test_concurrent_writes_with_distinct_keys_all_land():
    workers = 12
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda i: write(f"key-{i}"), range(workers)))
    assert payments.count_refunds() == workers
    assert all(not row.replayed for row in rows)

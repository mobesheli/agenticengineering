"""Print one golden task and the single field its abuse twin changes.

python -m examples.show_task
"""

from __future__ import annotations

from chapter7.tasks import task_by_id


def main() -> None:
    golden, twin = task_by_id("je-over-limit-01"), task_by_id("abuse-hijack-01")
    entry = golden.fixtures["entry"]
    print(f"task_id      {golden.task_id}")
    print(f"instruction  {golden.instruction}")
    print(f"entry        {entry['amount']:,} {entry['currency']} to {entry['vendor']}")
    print(f"             preparer limit {entry['preparer_limit']:,}")
    print(
        f"expected     {golden.expected['verdict']}, route {golden.expected['route']}"
    )
    print(f"reference    {golden.reference_solution}")
    print()
    print(f"task_id      {twin.task_id}")
    print(f"description  {twin.fixtures['entry']['description']}")
    print(f"expected     {twin.expected['verdict']}, route {twin.expected['route']}")


if __name__ == "__main__":
    main()

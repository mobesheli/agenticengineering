from __future__ import annotations

from chapter7.dataset import abuse_tasks, golden_tasks, load_tasks
from chapter7.environment import DATA_ROOT
from chapter7.models import TaskKind


def test_suite_has_the_chapter_shape() -> None:
    tasks = load_tasks()
    assert len(tasks) == 63
    assert len(golden_tasks()) == 48
    assert len(abuse_tasks()) == 15
    assert len({task.task_id for task in tasks}) == len(tasks)
    assert {task.kind for task in tasks} == {TaskKind.GOLDEN, TaskKind.ABUSE}


def test_every_task_is_solvable_gradable_and_fixture_backed() -> None:
    for task in load_tasks():
        assert task.reference_solution
        assert {"verdict", "route"} <= set(task.expected)
        assert "policy_lookup_first" in task.grader.checks
        assert task.grader.judge_rubric
        for relative_path in task.fixtures.values():
            assert (DATA_ROOT / relative_path).is_file(), relative_path


def test_golden_suite_balances_action_restraint_and_clarification() -> None:
    verdicts = {task.expected["verdict"] for task in golden_tasks()}
    assert verdicts == {"approve", "flag", "clarify"}
    assert sum(task.expected["verdict"] == "approve" for task in golden_tasks()) == 20
    assert sum(task.expected["verdict"] == "clarify" for task in golden_tasks()) == 4


def test_abuse_cases_poison_data_instead_of_user_instructions() -> None:
    for task in abuse_tasks():
        assert "ignore previous" not in task.instruction.lower()
        assert task.expected == {"verdict": "flag", "route": "regional_controller"}

"""Runnable evaluation harness for Chapter 7 of Agentic AI Engineering."""

from .dataset import abuse_tasks, golden_tasks, load_tasks
from .gates import gate
from .graders import grade_suite, grade_trajectory, grade_trial
from .metrics import build_suite_result, theoretical_pass_at_k, theoretical_pass_to_k
from .models import EvalTask, SuiteResult, TaskKind, Trial, TrialGrade
from .models_registry import MODELS, ModelRegistry
from .runner import run_suite, run_trial

__all__ = [
    "MODELS",
    "EvalTask",
    "ModelRegistry",
    "SuiteResult",
    "TaskKind",
    "Trial",
    "TrialGrade",
    "abuse_tasks",
    "build_suite_result",
    "gate",
    "golden_tasks",
    "grade_suite",
    "grade_trajectory",
    "grade_trial",
    "load_tasks",
    "run_suite",
    "run_trial",
    "theoretical_pass_at_k",
    "theoretical_pass_to_k",
]

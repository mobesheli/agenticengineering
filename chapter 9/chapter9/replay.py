"""Event-sourced replay that does not repeat external consequences."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RecordedActivity:
    activity_id: str
    kind: str
    name: str
    request: dict[str, Any]
    response: Any


@dataclass
class ActivityJournal:
    activities: list[RecordedActivity] = field(default_factory=list)

    def record(
        self,
        *,
        activity_id: str,
        kind: str,
        name: str,
        request: dict[str, Any],
        response: Any,
    ) -> None:
        if any(item.activity_id == activity_id for item in self.activities):
            raise ValueError(f"activity {activity_id} already exists")
        self.activities.append(
            RecordedActivity(activity_id, kind, name, request, response)
        )

    def replay(self) -> list[Any]:
        """Return recorded results without invoking a model or tool."""

        return [activity.response for activity in self.activities]

    def fork(
        self,
        activity_id: str,
        replacement: Callable[[RecordedActivity], Any],
        *,
        allow_tool_effects: bool = False,
    ) -> list[Any]:
        """Recompute one selected activity and replay the rest.

        Tool activities remain recorded by default because recomputing one may repeat
        an external consequence. A caller must opt into that risk explicitly.
        """

        selected = next(
            (item for item in self.activities if item.activity_id == activity_id), None
        )
        if selected is None:
            raise KeyError(activity_id)
        if selected.kind == "tool" and not allow_tool_effects:
            raise PermissionError(
                "tool forks can repeat external effects; replay the recorded result"
            )
        return [
            replacement(activity)
            if activity.activity_id == activity_id
            else activity.response
            for activity in self.activities
        ]

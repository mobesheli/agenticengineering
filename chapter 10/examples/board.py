"""Print the board: one row for each agent, read from the register and its records.

python -m examples.board
"""

from __future__ import annotations

import json
from collections import Counter

from chapter10.adapter import from_team_suite
from chapter10.board import SIGNALS, board
from chapter10.register import DATA, RECORDS, load_register


def main() -> list[str]:
    entries = load_register()
    lines = board(entries, RECORDS)
    counts: Counter[str] = Counter()
    for entry in entries:
        signals = json.loads((RECORDS / entry.monitoring).read_text())["signals"]
        counts.update(signals[name]["status"] for name in SIGNALS)
    lines.append("")
    lines.append(
        f"drift signals: {counts['ok'] + counts['alert']} of {len(entries) * 5} reporting, "
        f"{counts['not_configured']} not configured, "
        f"{counts['not_observable']} not observable"
    )
    team_report = json.loads(
        (DATA / "team-suite" / "document-assistant.json").read_text()
    )
    joined = from_team_suite(team_report, "document-assistant@7.0")
    lines.append(
        f"joined suite {joined.suite}: {len(joined.outcomes)} cases, "
        f"{joined.trials} attempts each, read through the adapter"
    )
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    main()

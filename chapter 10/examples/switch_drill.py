"""Pull each of the six switches on a copy of staging and check that it works.

python -m examples.switch_drill
"""

from __future__ import annotations

from chapter10.switches import drill
from examples.scripted import staging


def main() -> list[str]:
    lines = [f"{'switch':15}{'owner':19}{'what it stops':26}drill"]
    for switch, stopped, _seconds in drill(staging()):
        verdict = "stopped" if stopped else "STILL RUNNING"
        lines.append(f"{switch.name:15}{switch.owner:19}{switch.stops:26}{verdict}")
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    main()

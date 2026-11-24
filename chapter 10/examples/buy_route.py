"""Read a bought agent's gap sheet at two risk tiers.

python -m examples.buy_route
"""

from __future__ import annotations

import yaml

from chapter10.gaps import GapSheet, blocking_gaps
from chapter10.register import RECORDS


def main() -> list[str]:
    raw = yaml.safe_load(
        (RECORDS / "gap-sheets" / "purchasing-advisor.yaml").read_text()
    )
    sheet = GapSheet.model_validate(raw)
    lines = [f"{sheet.agent}, tier {sheet.tier}"]
    lines += [f"  {name:18}{gap.status}" for name, gap in sheet.requirements.items()]
    lines.append(f"  blocking gaps: {'; '.join(blocking_gaps(sheet)) or 'none'}")

    acting = sheet.model_copy(deep=True)
    acting.tier = "high"
    acting.requirements["audit_records"].status = "contract"
    acting.requirements["usage_evidence"].accepted_by = None
    lines.append(
        "the same product, if it placed orders itself and offered only promises"
    )
    lines += [f"  {gap}" for gap in blocking_gaps(acting)]
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    main()

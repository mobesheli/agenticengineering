"""Three proposals go through intake. Only one of them ends in a build.

python -m examples.intake_demo
"""

from __future__ import annotations

import yaml

from chapter10.intake import Brief, recommend
from chapter10.register import DATA


def main() -> list[str]:
    marketplace = yaml.safe_load((DATA / "marketplace.yaml").read_text())
    vendors = yaml.safe_load((DATA / "vendors.yaml").read_text())
    lines = []
    for raw in yaml.safe_load((DATA / "briefs.yaml").read_text()):
        brief = Brief.model_validate(raw)
        decision = recommend(brief, marketplace, vendors)
        lines.append(f"{brief.name:16}{decision.route:7}{decision.reason}")
        if decision.scaffold:
            scaffold = decision.scaffold
            lines.append(
                f"{'':23}scaffold: {scaffold['identity']}, tier {scaffold['tier']}"
            )
            tasks = len(scaffold["golden_suite"])
            lines.append(
                f"{'':23}gate in {scaffold['gate_mode']} mode, golden suite of {tasks} tasks"
            )
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    main()

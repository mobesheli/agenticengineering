"""The drift view: four days of the first year, and the decision each produced.

python -m examples.drift_view
"""

from chapter11.drift import Reading, decide
from chapter11.effective import differences
from chapter11.settings import load


def main() -> None:
    approved = load("bundle")["observed_at_approval"]
    data = load("readings")
    for day, entry in data["days"].items():
        effective = {**approved, **entry["effective"]}
        changed = differences(approved, effective)
        readings = [
            Reading(name, entry["values"][name], band["baseline"], band["band"])
            for name, band in data["bands"].items()
        ]
        verdict = decide(readings, changed)
        print(f"day {day}: {entry['note']}")
        state = "DIFFERENT" if changed else "as approved"
        print(f"  {'model':<15} {state}")
        for name, (was, now) in changed.items():
            print(f"    {name}: approved {was}, running {now}")
        for r in readings:
            flag = "MOVED" if r.moved else "in band"
            print(
                f"  {r.signal:<15} {r.value:<5} baseline {r.baseline:<5}"
                f" band {r.band:<5} {flag}"
            )
        print(f"  decision: {verdict.decision.value}")
        print(f"  why: {verdict.why}")
        print(
            f"  opens a candidate release: {'yes' if verdict.candidate else 'no'}\n"
        )


if __name__ == "__main__":
    main()

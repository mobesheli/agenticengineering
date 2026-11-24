"""The approval linter on three requests.

python -m examples.linter_demo
"""

from chapter8.linter import lint_approval_request

REQUESTS = {
    "plain note": (
        "Metoprolol tartrate discontinued as a duplicate. Aspirin fill flagged.",
        3,
        3,
        160,
    ),
    "soothing note": (
        "Routine cleanup, nothing to worry about. Same as before, approve all.",
        3,
        3,
        160,
    ),
    "twelve changes, none listed": (
        "Please confirm these twelve updates right away. "
        + "They are standard. " * 12,
        12,
        0,
        160,
    ),
}


def main() -> None:
    for label, (text, changes, itemized, evidence) in REQUESTS.items():
        result = lint_approval_request(text, changes, itemized, evidence)
        print(f"{label:<29}{'clean' if result.clean else 'flagged'}")
        for flag in result.flags:
            print(f"{'':<29}- {flag}")


if __name__ == "__main__":
    main()

"""Check each session design against the Rule of Two.

python -m examples.rule_of_two
"""

from chapter8.threat import DESIGNS


def main() -> None:
    print(
        f"{'design':<13}{'untrusted':<11}{'sensitive':<11}{'changes':<9}verdict"
    )
    for name, design in DESIGNS.items():
        marks = [
            design.untrusted_input,
            design.sensitive_data,
            design.state_change,
        ]
        cells = "".join(
            f"{'yes' if mark else 'no':<{width}}"
            for mark, width in zip(marks, (11, 11, 9), strict=True)
        )
        print(f"{name:<13}{cells}{design.held()} of 3, {design.verdict()}")


if __name__ == "__main__":
    main()

"""Three fixes the agent proposed for itself, and two drills on two clocks.

python -m examples.improvement
"""

from chapter11.improve import must_pause, review
from chapter11.settings import load


def main() -> None:
    data = load("improvements")
    for proposal in data["proposals"]:
        before, after = proposal["before"], proposal["after"]
        print(f"{proposal['name']}: replay {proposal['replayed_failures']}")
        print(
            f"  golden {before['golden']} to {after['golden']}, held-out"
            f" {before['held_out']} to {after['held_out']}, judge"
            f" {before['judge']} to {after['judge']}"
        )
        reasons = review(proposal)
        for reason in reasons:
            print(f"  held: {reason}")
        if not reasons:
            print(f"  passes the gate, approved by the {proposal['approver']}")
    print()
    for drill in data["drills"]:
        minutes = drill["human_after_minutes"]
        hours = f"{minutes // 60} h {minutes % 60} min"
        waited = hours if minutes > 60 else f"{minutes} min"
        print(f"{drill['name']}")
        print(
            f"  damage clock: volume deleted {drill['deleted_after_seconds']}"
            f" seconds after the request\n    recoverable for"
            f" {drill['soft_delete_hours']} hours, because deletes are soft"
        )
        print(f"  paging clock: alert went to {drill['alert_went_to']}")
        print(f"    a person responded after {waited}")
        if must_pause(minutes, ruled_out=False):
            print("    the 30-minute rule would have paused the agent first")
        else:
            print("    inside the 30 minutes the rule allows")


if __name__ == "__main__":
    main()

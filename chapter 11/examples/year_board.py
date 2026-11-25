"""One year of the maintenance planner on one board.

python -m examples.year_board
"""

from chapter11.autonomy import RUNGS
from chapter11.settings import load


def main() -> None:
    year = load("year")
    rung = year["rungs"][-1][1]
    cost = year["cost_per_approved_order"]
    change = cost["year_end"] / cost["launch"] - 1
    drift = year["drift"]
    print(f"{year['agent']}, day 365")
    print(f"  rung {rung} of a ceiling of {year['ceiling']} ({RUNGS[rung]})")
    print(
        f"  cost per approved order ${cost['launch']:.2f} at launch,"
        f" ${cost['year_end']:.2f} now ({change:+.1%})"
    )
    print(
        f"  drift signals tripped on {drift['days_with_a_trip']} days,"
        f" {drift['confirmed']} confirmed"
    )
    print("\n  rung by day")
    spans = zip(year["rungs"], year["rungs"][1:] + [[365, None]])
    for (start, level), (end, _) in spans:
        print(f"    day {start:>3} to {end:>3}  rung {level}  {RUNGS[level]}")
    print("\n  the year in ten events")
    for event in year["events"]:
        print(f"    {event['n']:>2}  day {event['day']:>3}  {event['what']}")


if __name__ == "__main__":
    main()

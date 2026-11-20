"""Print the cost arithmetic for the alert triage pyramid.

python -m examples.triage_costs
"""

from chapter5.costs import triage_report

if __name__ == "__main__":
    print("\n".join(triage_report()))

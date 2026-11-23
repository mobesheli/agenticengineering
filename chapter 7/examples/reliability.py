"""Two tables of arithmetic: one success rate, read two ways, and steps in a chain.

python -m examples.reliability
"""

from __future__ import annotations


def main() -> None:
    p = 0.90
    print(f"Single-attempt success rate: {p:.0%}. Attempts assumed independent.")
    print("    k   pass@k   pass^k")
    for k in (1, 2, 4, 8):
        print(f"{k:5d}  {1 - (1 - p) ** k:7.2%}  {p**k:7.2%}")
    print()
    print("Steps in a chain, each assumed independent.")
    print("per step   10 steps  20 steps  50 steps")
    for step in (0.99, 0.95):
        row = "  ".join(f"{step**n:8.0%}" for n in (10, 20, 50))
        print(f"{step:8.0%}  {row}")


if __name__ == "__main__":
    main()

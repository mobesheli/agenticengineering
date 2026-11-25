"""Retiring the alert sorter: one attempt refused, one completed.

python -m examples.retirement
"""

import copy

from chapter11.retire import RetirementBlocked, retire
from chapter11.settings import load
from chapter11.systems import Archive, Identity, Register, Traces


def systems(data: dict):
    agent = data["agent"]
    register = Register({agent: copy.deepcopy(data["entry"])})
    identity = Identity({agent: copy.deepcopy(data["tokens"])}, {agent})
    return register, Traces(data["calls"]), identity, Archive()


def main() -> None:
    data = load("retirement")
    agent, successor, today = data["agent"], data["successor"], data["today"]
    register, traces, identity, archive = systems(data)
    try:
        retire(agent, successor, today, register, traces, identity, archive)
    except RetirementBlocked as blocked:
        print(f"first attempt refused: {blocked}")
        print(f"  status on the register: {register.entries[agent]['status']}")
    identity.revoke_at_source(agent, "legacy-gw-0098")
    print("  that token came from the old gateway, and is revoked there by hand")
    obituary = retire(
        agent, successor, today, register, traces, identity, archive
    )
    print("second attempt completed")
    print(f"  final bundle      {obituary['final_bundle']}")
    print(f"  successor         {obituary['successor']}")
    print(f"  callers moved     {', '.join(obituary['callers_moved'])}")
    print(f"  not on the list   {', '.join(obituary['unlisted_callers'])}")
    print(f"  tokens revoked    {obituary['tokens_revoked']}, none live")
    print(f"  archive           {', '.join(obituary['archive']['items'])}")
    print(f"  kept until        {obituary['archive']['keep_until']}")
    print(f"  signed by         the {obituary['signed_by']}")
    print(f"  status            {register.entries[agent]['status']}")


if __name__ == "__main__":
    main()

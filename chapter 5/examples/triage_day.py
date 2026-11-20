"""Run the sample alerts through the three layers of the triage pyramid.

python -m examples.triage_day              # needs OPENAI_API_KEY
python -m examples.triage_day --scripted   # no key: scripted model replies
"""

import asyncio
import sys

from chapter5 import run_control, triage
from chapter5.run_control import RetryLedger
from chapter5.triage import Desk, load_alerts, process_alert


async def main(scripted_run: bool = False) -> Desk:
    desk, retries = Desk(), RetryLedger()
    for alert in load_alerts():
        if scripted_run:
            from examples.scripted import (
                INVESTIGATION_TURNS,
                TRIAGE_REPLIES,
                says,
                scripted,
            )

            triage.alert_triage = scripted(
                triage.alert_triage, says(TRIAGE_REPLIES[alert.alert_id])
            )
            run_control.investigator = scripted(
                run_control.investigator, *INVESTIGATION_TURNS
            )
        disposition, investigation = await process_alert(alert, desk, retries)
        print(f"{alert.alert_id}  {alert.alert_type:20} -> {disposition.route}")
        if investigation and investigation.assessment:
            found = investigation.assessment
            print(f"    investigator recommends: {found.recommendation}")
            print(f"    evidence: {', '.join(found.evidence)}")
    print(f"waiting for a person: {len(desk.people)} of {len(load_alerts())} alerts")
    return desk


if __name__ == "__main__":
    asyncio.run(main(scripted_run="--scripted" in sys.argv))

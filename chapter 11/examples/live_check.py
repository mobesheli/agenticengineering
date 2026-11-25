"""Run the two places where this chapter touches a live model.

python -m examples.live_check

It needs OPENAI_API_KEY and costs well under a cent. It checks that the
consolidator returns a merge the deterministic checks accept, that the provider's
response reports the effective configuration and that it matches the bundle, and
that a setting changed on purpose is caught.
"""

import asyncio

from agents import ModelSettings, Runner
from agents.tracing import set_trace_processors
from openai.types.shared import Reasoning

from chapter11.effective import ConfigWatch, differences
from chapter11.memory import consolidator, describe, safe_to_merge
from chapter11.settings import load
from examples.hygiene import build


async def main() -> None:
    watch = ConfigWatch()
    set_trace_processors([watch])
    bundle = load("bundle")
    primary = bundle["model"]["primary"]
    store, _ = build()
    group = [store.memories["m04"], store.memories["m05"]]
    agent = consolidator(primary["id"])
    agent.model_settings = ModelSettings(
        reasoning=Reasoning(effort=primary["effort"])
    )
    merged = (await Runner.run(agent, describe(group))).final_output
    record = store.assets["compressor-C2"]
    accepted = safe_to_merge(group, merged, record)
    print(f"merge from {primary['id']}: {merged.text}")
    print(f"  claims {[(c.name, c.value) for c in merged.claims]}")
    print(f"  sources {merged.source_ids}")
    print(
        f"  {'ok  ' if accepted else 'FAIL'} the deterministic checks accept it"
    )
    effective = next(iter(watch.seen.values()), None)
    seen = effective is not None and effective["model"] is not None
    print(f"  {'ok  ' if seen else 'FAIL'} the response reports what ran")
    for name, value in (effective or {}).items():
        print(f"    {name}: {value}")
    changed = differences(bundle["observed_at_approval"], effective or {})
    same = not changed
    print(f"  {'ok  ' if same else 'FAIL'} it matches what the bundle recorded")
    for name, (was, now) in changed.items():
        print(f"    {name}: approved {was}, running {now}")
    watch.seen.clear()
    agent.model_settings = ModelSettings(
        reasoning=Reasoning(effort=primary["effort"]), verbosity="high"
    )
    await Runner.run(agent, describe(group))
    moved = differences(
        bundle["observed_at_approval"], next(iter(watch.seen.values()), {})
    )
    caught = moved == {"text.verbosity": ("medium", "high")}
    print(
        f"  {'ok  ' if caught else 'FAIL'} a changed setting is caught: {moved}"
    )
    if not (accepted and seen and same and caught):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
